# Overview

This is a comprehensive farm expense management system designed to help farmers track fertilizer purchases, manage suppliers, monitor field operations, and analyze expenses. The application includes an AI-powered farming assistant using Google's Gemini API to provide personalized agricultural advice based on user data.

The system supports both simple fertilizer tracking and comprehensive expense management, allowing farmers to monitor costs per acre, categorize expenses, manage multiple fields, and maintain supplier relationships. It includes user authentication, admin functionality, data import/export capabilities, and responsive design optimized for mobile devices.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask
- **UI Framework**: Bootstrap 5.1.3 for responsive design
- **Mobile-First Design**: Touch-friendly interface optimized for mobile devices
- **Icons**: Font Awesome 6.0.0 for consistent iconography
- **JavaScript**: Vanilla JavaScript for form interactions and dynamic content

## Backend Architecture
- **Web Framework**: Flask with modular structure
- **Authentication**: Flask-Login for session management
- **Forms**: WTForms with Flask-WTF for form handling and validation
- **File Handling**: Werkzeug for secure file uploads (CSV import)
- **Password Security**: Werkzeug password hashing utilities

## Data Models
- **User Model**: Authentication with role-based access (admin/user)
- **Bills & Fertilizers**: Transactional fertilizer purchase tracking
- **Comprehensive Expenses**: Extended expense categorization system
- **Suppliers**: Vendor management with contact information
- **Fields**: Farm plot management with area tracking

## Data Storage
- **Primary Database**: SQLite with SQLAlchemy ORM
- **Relationships**: Comprehensive foreign key relationships with cascade deletion
- **Data Integrity**: Database constraints and validation

## AI Integration
- **AI Assistant**: Google Gemini API integration for farming advice
- **Structured Responses**: Pydantic models for consistent AI output
- **Context-Aware**: Utilizes user expense and field data for personalized recommendations

## Security & Access Control
- **Authentication**: Email-based login with password hashing
- **Authorization**: Role-based access with admin dashboard
- **Session Management**: Flask sessions with configurable secret keys
- **Input Validation**: Server-side validation for all user inputs

# External Dependencies

## AI Services
- **Google Gemini API**: AI-powered farming assistant and expense analysis
- **API Key**: Environment variable `GEMINI_API_KEY` required

## Frontend Libraries
- **Bootstrap 5.1.3**: CSS framework via CDN
- **Font Awesome 6.0.0**: Icon library via CDN

## Python Dependencies
- **Flask**: Web framework with SQLAlchemy, Login, and WTF extensions
- **Werkzeug**: WSGI utilities and security functions
- **Pydantic**: Data validation for AI responses
- **Google GenAI**: Gemini API client library

## Database
- **SQLite**: Default database (configurable via `SQLALCHEMY_DATABASE_URI`)
- **SQLAlchemy**: ORM with relationship management

## Environment Configuration
- **SESSION_SECRET**: Flask session security key
- **GEMINI_API_KEY**: Required for AI functionality
- **SQLALCHEMY_DATABASE_URI**: Database connection string

## File Processing
- **CSV Import/Export**: Native Python csv module
- **File Upload**: Werkzeug secure filename handling
- **Data Validation**: Custom validation for imported data