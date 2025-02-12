# .cursorrules

## Project Overview

*   **Type:** cursorrules_file
*   **Description:** I want to build a Web site with Flask for a total beauty shop with photo galleries. The main page includes photos of the shop. Pages should be made in Korean language.

샵의 이름은 'Stylegrapher 스타일그래퍼'입니다.

서비스 상품 종류는 다음과 같습니다: 개인화보, 프로필화보, 메이크업 레슨, 퍼스널 컬러 진단, 메이크업/헤어스타일링, 패션 스타일링

서비스 가격표를 함께 제공합니다.

*   **Primary Goal:** Attract new clients by showcasing high-quality photo galleries and detailed service information in an elegant, user-friendly layout that supports future multilingual enhancements.

## Project Structure

### Framework-Specific Routing

*   **Directory Rules:**

    *   Flask (Latest): Utilize Flask's built-in routing, with an application factory pattern and Blueprints to organize endpoints.
    *   Example: Main routes defined in a central app.py and modular routes placed in a dedicated 'routes/' folder if using Blueprints.

### Core Directories

*   **Versioned Structure:**

    *   templates: Holds HTML templates (landing page, service information pages, gallery, booking/contact forms) rendered by Flask.
    *   static: Contains static assets such as CSS, JavaScript, and images (emphasizing the high-quality photo gallery and purple-themed design).
    *   admin: Dedicated folder for admin interface templates and views to manage service details, gallery updates, and pricing information.

### Key Files

*   **Stack-Versioned Patterns:**

    *   app.py: The main Flask application entry point configuring routes and initializing the application.
    *   admin.py: Handles the admin interface routes and logic for content management.
    *   templates/index.html: Landing page template highlighting 'Stylegrapher 스타일그래퍼' with a focus on elegance and visual impact.
    *   static/css/main.css: Primary stylesheet enforcing the purple color scheme and modern design aesthetics.

## Tech Stack Rules

*   **Version Enforcement:**

    *   <Flask@2.x>: Implement routing via an application factory and Blueprints to ensure modular code organization.
    *   <SQLite@3.x>: Adhere to standard SQLite practices for managing service details and booking data, with file system-based image storage.

## PRD Compliance

*   **Non-Negotiable:**

    *   "The main goal of the website is to attract new clients by displaying visually engaging photo galleries and professional service descriptions." : The website must include a robust admin interface for real-time updates, a booking/contact form with instant follow-up communication, and adhere to the elegant, purple-themed visual identity.

## App Flow Integration

*   **Stack-Aligned Flow:**

    *   Flask Routing Flow → Define routes within app.py and via Blueprints for landing, service details, gallery, and booking pages. The admin interface is secured and accessible via a dedicated route such as '/admin', ensuring smooth navigation between public and admin sections.
