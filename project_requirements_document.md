# Project Requirements Document (PRD)

## 1. Project Overview

Stylegrapher 스타일그래퍼 is a beautifully designed website for a total beauty shop that showcases high-quality service photography and detailed information about a variety of beauty and style services. The site is built using Flask and will cater primarily to Korean-speaking clients while offering an elegant experience through its luxurious purple-themed design. It highlights everything from personal and profile photoshoots to makeup lessons, personal color diagnosis, hair and makeup styling, and fashion styling — presenting not only the creative work of the shop but also clear pricing details.

The main goal of the website is to attract new clients by displaying visually engaging photo galleries and professional service descriptions, while also providing current customers an easy way to access essential information and book appointments. The project is arranged to allow the admin to update photos and service information regularly via a dedicated interface. Additionally, the site plans for future language support and integrates key social media platforms like Instagram and YouTube to expand its reach and maintain an optimal SEO performance.

## 2. In-Scope vs. Out-of-Scope

**In-Scope:**

*   A Flask-based website designed with a modern, elegant layout using purple as the main color.
*   A visually engaging landing page that highlights high-quality images of the shop.
*   Detailed service information pages covering personal photoshoots, makeup lessons, styling services, and clear pricing details.
*   A photo gallery page that displays regularly updated images, managed by an admin.
*   A booking and contact page with a form where users can submit reservation inquiries and receive follow-up calls or KakaoTalk messages.
*   An admin interface for managing service details, gallery images, and pricing.
*   Social media integrations with Instagram and YouTube.
*   Basic SEO optimization and provisions for future multilingual support.

**Out-of-Scope:**

*   E-commerce functionality or payment processing features.
*   Advanced user account management or user dashboards.
*   Any non-Korean language content beyond planned future multilingual support.
*   Development of an in-depth CMS beyond the basic admin interface requirements.

## 3. User Flow

When a visitor first lands on the website, they are greeted with a stunning landing page that prominently features the Stylegrapher 스타일그래퍼 branding and high-quality photos of the beauty shop. The homepage emphasizes the shop’s luxurious ambiance and professional services with a clean design and bold purple accents. From here, users can immediately grasp the shop’s identity and the high standard of the services provided.

As users navigate the site, they can explore detailed service pages with pricing information and breathtaking photo galleries. When they are interested in booking a service, they move on to the reservation page where a clear and intuitive contact form is available. After submitting their details, users receive a confirmation message stating that a representative from Stylegrapher will reach out via phone or KakaoTalk. This seamless journey, from initial discovery to booking, is designed to keep the experience straightforward and pleasant.

## 4. Core Features

*   **Landing Page:**\
    • Visually appealing introductory page displaying the shop’s name and high-quality images.\
    • Prominent use of purple and an elegant design to reflect luxury.
*   **Service Information Pages:**\
    • Detailed descriptions of services (개인화보, 프로필화보, 메이크업 레슨, 퍼스널 컬러 진단, 메이크업/헤어스타일링, 패션 스타일링).\
    • Clear pricing tables and service breakdowns all provided in Korean.
*   **Photo Gallery:**\
    • A curated gallery displaying high-resolution images of the shop and sample work.\
    • Regular updates managed through an admin interface.
*   **Booking/Contact Form:**\
    • An intuitive form allowing users to schedule appointments or make inquiries.\
    • Immediate confirmation and follow-up message regarding post-booking communication (phone or KakaoTalk).
*   **Admin Interface:**\
    • Backend panel for managing service details, updating photo galleries, and maintaining pricing information.\
    • Use of SQLite for data storage and file system for image hosting.
*   **Social Media Integration:**\
    • Integration with Instagram and YouTube APIs to display feeds and enhance SEO visibility.
*   **SEO and Future Multilingual Support:**\
    • Optimization for search engines to drive organic traffic.\
    • Planning for multilingual support to accommodate a global audience in future releases.

## 5. Tech Stack & Tools

*   **Frontend:**\
    • HTML/CSS with modern design practices.\
    • JavaScript for interactivity if needed (basic animations or form validations).
*   **Backend:**\
    • Python with Flask for the web framework.\
    • SQLite as the database for storing service details, appointments, and pricing information. • Filesystem storage for hosting image files.
*   **API and Third-Party Integrations:**\
    • Instagram API integration for photo feeds.\
    • YouTube API to embed or showcase video content.
*   **Development Tools:**\
    • Cursor – advanced IDE for AI-powered coding with real-time suggestions.

## 6. Non-Functional Requirements

*   **Performance:**\
    • The website should load quickly (ideally within 2-3 seconds) even with high-quality images.\
    • Backend queries (SQLite) must be optimized for fast retrieval of service information and images.
*   **Security:**\
    • Secure handling of form data with proper validations and protection against common web vulnerabilities (e.g., SQL injection, CSRF).\
    • Secure admin interface authentication.
*   **Usability:**\
    • The design should cater to an elegant, visually engaging experience and be responsive for various devices.\
    • The navigation must be intuitive with clear layouts to ensure ease of use for visitors.
*   **SEO:**\
    • Adherence to SEO best practices to ensure high search engine rankings.
*   **Accessibility:**\
    • Ensure the site is accessible with appropriate contrast levels, alt texts for images, and reliable navigation for users with disabilities.

## 7. Constraints & Assumptions

*   **Constraints:**\
    • The website is developed using Flask with SQLite and filesystem for images, which may limit scalability compared to larger databases in the future.\
    • Admin interface is assumed to be basic, focusing on ease-of-use rather than advanced CMS features.
*   **Assumptions:**\
    • The server environment supports Python/Flask and has access to the filesystem for image storage.\
    • Admin users have basic technical skills to manage the content through the backend interface.\
    • Future multilingual support will be implemented with a plan to update text content and possibly use translation libraries or services.\
    • Social media API keys and integration details will be provided and are assumed to be maintained/updated as required.

## 8. Known Issues & Potential Pitfalls

*   **Image Management:**\
    • Regular updates of the photo gallery require an easy-to-use admin interface. Poorly optimized image uploads may slow down the site.
*   **Social Media Integrations:**\
    • API rate limits or changes in external services (Instagram, YouTube) could affect content display. It's important to include error handling and caching strategies.
*   **SEO & Performance:**\
    • High-resolution images and dynamic content from APIs might impact load times. Techniques like image compression, lazy loading, and caching should be considered.
*   **Admin Interface Security:**\
    • With an open interface to update content, proper authentication and security measures are critical to avoid unauthorized changes.
*   **Future Multilingual Support:**\
    • Planning for additional languages now is essential to ensure the website’s structure is adaptable; any hard-coded text should be prepared for easy translation without significant code changes.

This document should serve as the definitive guide for all future technical documents, ensuring that the project is well-understood and implemented with no ambiguity.
