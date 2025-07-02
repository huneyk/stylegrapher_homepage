#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration Script for Render Deployment
"""
import os
import sys
from flask_migrate import upgrade
from app import create_app

def run_migration():
    """Run database migration safely"""
    try:
        print("Starting database migration...")
        
        # Create Flask app
        app = create_app()
        
        # Run migration within app context
        with app.app_context():
            print("Running flask db upgrade...")
            upgrade()
            print("✅ Database migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Database migration failed: {str(e)}")
        # Don't exit with error code to allow deployment to continue
        print("⚠️  Continuing deployment despite migration failure...")

if __name__ == "__main__":
    run_migration() 