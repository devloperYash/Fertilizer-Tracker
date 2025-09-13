import json
import logging
import os
from datetime import datetime, date
from collections import defaultdict
import pytz
import markdown

from google import genai
from google.genai import types
from pydantic import BaseModel

# IMPORTANT: This file uses the Gemini integration
# Initialize Gemini client with API key
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

class FarmingInsight(BaseModel):
    """Structured farming insight response"""
    insight_type: str
    title: str
    message: str
    actionable_tip: str
    confidence: float

class ExpenseAnalysis(BaseModel):
    """Structured expense analysis"""
    total_expenses: float
    cost_per_acre: float
    top_expense_category: str
    recommendation: str
    efficiency_score: int  # 1-10

class FarmingAssistant:
    """AI-powered farming assistant using Gemini"""
    
    def __init__(self):
        self.client = client
        
    def get_indian_timezone_now(self):
        """Get current time in Indian timezone"""
        indian_tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(indian_tz)
    
    def is_farming_related(self, question):
        """Check if the question is farming-related"""
        farming_keywords = [
            'farm', 'farming', 'crop', 'crops', 'fertilizer', 'pesticide', 'seed', 'seeds',
            'agriculture', 'agricultural', 'soil', 'irrigation', 'harvest', 'plant', 'planting',
            'wheat', 'rice', 'cotton', 'sugarcane', 'corn', 'maize', 'barley', 'soybean',
            'kharif', 'rabi', 'zaid', 'monsoon', 'weather', 'expense', 'cost', 'budget',
            'field', 'plot', 'acre', 'hectare', 'yield', 'production', 'market', 'price',
            'subsidy', 'scheme', 'government', 'organic', 'bio', 'compost', 'manure',
            'tractor', 'equipment', 'machinery', 'storage', 'processing', 'supply', 'supplier'
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in farming_keywords)
        
    def analyze_expenses(self, user_expenses, user_fields=None, user_info=None):
        """Analyze user's expense data and provide insights"""
        try:
            # Prepare expense data summary
            total_expenses = sum(exp.total_amount for exp in user_expenses)
            category_breakdown = defaultdict(float)
            recent_expenses = []
            
            for expense in user_expenses:
                category_breakdown[expense.category] += expense.total_amount
                if expense.expense_date and expense.expense_date >= date.today().replace(month=date.today().month-1):
                    recent_expenses.append({
                        'description': expense.description,
                        'category': expense.category,
                        'amount': expense.total_amount,
                        'date': expense.expense_date.strftime('%Y-%m-%d') if expense.expense_date else None
                    })
            
            # Calculate per acre costs if field data available
            total_acres = sum(field.area_acres for field in user_fields) if user_fields else 0
            cost_per_acre = total_expenses / total_acres if total_acres > 0 else 0
            
            # Prepare context for AI
            context = f"""
            Analyze this Indian farmer's expense data and provide actionable insights:
            
            Total Expenses: ₹{total_expenses:,.2f}
            Total Farm Area: {total_acres} acres
            Cost per Acre: ₹{cost_per_acre:,.2f}
            
            Category Breakdown:
            {json.dumps(dict(category_breakdown), indent=2)}
            
            Recent Expenses (last 30 days):
            {json.dumps(recent_expenses, indent=2)}
            
            Farm Location: {user_info.location if user_info and user_info.location else 'Not specified'}
            Farm Name: {user_info.farm_name if user_info and user_info.farm_name else 'Not specified'}
            
            Provide specific, practical advice for Indian farming conditions. Focus on:
            1. Cost optimization opportunities
            2. Spending pattern insights
            3. Seasonal recommendations
            4. Input efficiency improvements
            """
            
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[context],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1000
                )
            )
            
            return response.text if response.text else "Unable to analyze expenses at this time."
            
        except Exception as e:
            logging.error(f"Error analyzing expenses: {e}")
            return "I'm having trouble analyzing your expenses right now. Please try again later."
    
    def get_farming_advice(self, question, user_context=None):
        """Provide farming advice based on user question and context"""
        try:
            # Check if question is farming-related
            if not self.is_farming_related(question):
                return """I'm a specialized AI assistant focused on helping Indian farmers with agricultural questions. 
                
I can help you with:
• 🌾 Crop planning and seasonal advice
• 💰 Expense analysis and cost optimization
• 🚜 Farm equipment and machinery guidance
• 🌱 Fertilizer, seed, and pesticide recommendations
• 🌧️ Weather and irrigation planning
• 📊 Market prices and government schemes
• 🔬 Soil management and organic farming

Please ask me questions related to farming, agriculture, or your farm expenses for the best assistance!"""
            
            system_prompt = """
            You are an AI farming assistant specialized EXCLUSIVELY in Indian agriculture. 
            
            STRICT GUIDELINES:
            - ONLY answer questions related to farming, agriculture, and farm management
            - Focus on Indian farming conditions, climate, and practices
            - Provide practical, actionable advice that Indian farmers can implement
            - Use markdown formatting for better readability (lists, bold text, etc.)
            - Include relevant emojis to make responses engaging
            
            CORE EXPERTISE AREAS:
            - Indian climate and seasons (Kharif, Rabi, Zaid)
            - Common Indian crops (rice, wheat, sugarcane, cotton, maize, etc.)
            - Cost-effective farming practices and expense optimization
            - Government schemes, subsidies, and support programs
            - Local market conditions and price trends
            - Sustainable and organic farming methods
            - Soil management, irrigation, and water conservation
            - Farm equipment, machinery, and technology
            - Pest management and crop protection
            - Storage, processing, and value addition
            
            RESPONSE FORMAT:
            - Use clear headings and bullet points
            - Provide specific, actionable steps
            - Include approximate costs in Indian Rupees where relevant
            - Mention regional variations when applicable
            - Reference government schemes or support when relevant
            
            Remember: You are helping Indian farmers improve their productivity, reduce costs, and increase profitability.
            """
            
            context = f"User Question: {question}"
            if user_context:
                context += f"\nUser Context: {user_context}"
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Content(role="user", parts=[types.Part(text=context)])],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=1000
                )
            )
            
            # Convert markdown to HTML for better formatting
            if response.text:
                # Process the response through markdown
                html_response = markdown.markdown(response.text, extensions=['tables', 'fenced_code'])
                return html_response
            else:
                return "I couldn't process your question right now. Please try again."
            
        except Exception as e:
            logging.error(f"Error getting farming advice: {e}")
            return "I'm having trouble providing advice right now. Please try again later."
    
    def generate_expense_report(self, user_expenses, period="monthly"):
        """Generate AI-powered expense reports"""
        try:
            # Group expenses by category and calculate insights
            category_totals = defaultdict(float)
            monthly_totals = defaultdict(float)
            
            for expense in user_expenses:
                category_totals[expense.category] += expense.total_amount
                if expense.expense_date:
                    month_key = expense.expense_date.strftime('%Y-%m')
                    monthly_totals[month_key] += expense.total_amount
            
            report_data = {
                'total_expenses': sum(exp.total_amount for exp in user_expenses),
                'category_breakdown': dict(category_totals),
                'monthly_trends': dict(monthly_totals),
                'expense_count': len(user_expenses)
            }
            
            context = f"""
            Generate a detailed expense report for this Indian farmer:
            
            {json.dumps(report_data, indent=2)}
            
            Create a comprehensive report with:
            1. Executive summary of spending
            2. Category-wise analysis with insights
            3. Monthly trends and patterns
            4. Recommendations for cost optimization
            5. Seasonal planning suggestions
            
            Format as a structured report suitable for farmers.
            """
            
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[context],
                config=types.GenerateContentConfig(
                    temperature=0.6,
                    max_output_tokens=1200
                )
            )
            
            return response.text if response.text else "Unable to generate report."
            
        except Exception as e:
            logging.error(f"Error generating expense report: {e}")
            return "Unable to generate report at this time."
    
    def predict_seasonal_expenses(self, user_expenses, current_season, user_fields=None):
        """Predict upcoming seasonal expenses based on historical data"""
        try:
            # Analyze historical seasonal patterns
            seasonal_expenses = defaultdict(list)
            
            for expense in user_expenses:
                if expense.season:
                    seasonal_expenses[expense.season].append({
                        'category': expense.category,
                        'amount': expense.total_amount,
                        'description': expense.description
                    })
            
            context = f"""
            Based on this farmer's historical expense data, predict upcoming seasonal expenses for {current_season}:
            
            Historical Seasonal Data:
            {json.dumps(dict(seasonal_expenses), indent=2)}
            
            Current Season: {current_season}
            Farm Area: {sum(f.area_acres for f in user_fields) if user_fields else 'Not specified'} acres
            
            Provide:
            1. Expected expense categories for this season
            2. Estimated budget requirements
            3. Priority expenses to plan for
            4. Cost-saving opportunities
            5. Timing recommendations for key purchases
            """
            
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[context],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1000
                )
            )
            
            return response.text if response.text else "Unable to predict seasonal expenses."
            
        except Exception as e:
            logging.error(f"Error predicting seasonal expenses: {e}")
            return "Unable to provide seasonal predictions at this time."

# Global instance
farming_assistant = FarmingAssistant()