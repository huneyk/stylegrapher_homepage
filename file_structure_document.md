# Introduction

The file structure of the project is the backbone that keeps everything organized and makes it simple for team members to work together. This document explains how we have arranged the files for the 'Stylegrapher 스타일그래퍼' website, a high-end beauty shop platform featuring photo galleries, detailed service information, and an integrated booking process. The structure is designed to support a visually engaging and elegant experience for Korean-speaking clients, while also planning ahead for future multilingual support.

# Overview of the Tech Stack

Our project is built with Flask as the primary web framework, which drives the server-side logic and routing. Data is stored using SQLite for a lightweight, file-based database, and all images are hosted within the filesystem. The use of Cursor provides an advanced development environment with real-time suggestions, making our coding process smoother. In addition, we integrate with social media platforms like Instagram, YouTube, and Thread to enhance engagement and SEO, ensuring that our site remains modern and easy to update. The chosen tech stack directly influences the file organization by separating backend logic, templates, static files, and configuration settings into clearly defined directories.

# Root Directory Structure

At the root level, several key directories and files define how the project is organized. The main file that bootstraps the Flask application, typically named app.py or run.py, is located here. The configuration files like config.py and .env for environment variables also reside at the root. There is a dedicated directory for the core application code, often named 'app' or 'src', which contains all routing, models, forms, and controllers related to the site. Additional directories include 'static' for CSS, JavaScript, and images, and 'templates' for HTML files that provide the structure for webpages such as the landing page, service details page, photo gallery, and booking/contact form. This clear separation helps in managing and locating specific files quickly.

# Configuration and Environment Files

Configuration files are essential in setting up the project environment. The file config.py holds key settings for development, testing, and production, defining variables such as database connections and API keys. Environment-specific settings are stored in a .env file, making it easy to change credentials or other sensitive information without modifying the code. Files like .flaskenv may also be present to set Flask-specific environment variables. These configurations ensure that the application behaves as expected in different scenarios while keeping the setup secure and maintainable.

# Documentation Structure

Documentation plays a crucial role in ensuring that everyone working on the project is on the same page. All project-related documents, including the project requirements, app flow details, technical stack explanations, and implementation plans, are stored within a dedicated 'docs' directory. This includes user guides, API documentation, and developer notes. Maintaining documentation alongside code enables better quality assurance, easier onboarding of new team members, and a reliable reference for future improvements or debugging sessions.

# Conclusion and Overall Summary

In summary, the file structure of this project has been carefully designed to support the unique needs of a high-end beauty shop website. The separation of application logic in the core directories, clear configuration settings, and detailed documentation ensures that the project is easy to navigate, update, and maintain. With Flask powering the backend and a robust admin interface for managing service details and images, the structure not only supports an elegant user experience in Korean but also positions the project for future enhancements like multilingual support and expanded social media integration. This organized framework stands out by balancing clarity with functionality, paving the way for efficient collaboration and continual growth.
