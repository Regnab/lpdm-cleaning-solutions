/* =====================================================================
   LPD&M Cleaning Solutions - Frontend JavaScript
   ---------------------------------------------------------------------
   Architecture:
   - All UI state managed client-side (no fake success simulations)
   - Forms intercepted via Fetch API to a configurable backend endpoint
   - Graceful degradation: failed API calls surface a phone/WhatsApp
     fallback banner instead of pretending success
   ===================================================================== */

/* =====================================================================
   1. CONFIGURATION
   ---------------------------------------------------------------------
   Backend team: change API_QUOTE_ENDPOINT here when wiring to Flask.
   For local dev against the Flask backend, this can be overridden via
   `window.LPDM_CONFIG = { API_QUOTE_ENDPOINT: '/api/v1/quote' }` in a
   small inline script BEFORE this file loads.
   ===================================================================== */
const CONFIG = Object.freeze(Object.assign({
    // Production endpoint (placeholder until backend is live)
   API_QUOTE_ENDPOINT: 'https://YOUR_API_GATEWAY_ID.execute-api.eu-west-2.amazonaws.com/v1/quote',

    // Network timeout in ms — protects users from indefinite spinners
    REQUEST_TIMEOUT_MS: 12000,

    // Public business contact — used by the failure-fallback banner
    BUSINESS_PHONE: '+447495687854',
    BUSINESS_PHONE_DISPLAY: '+44 7495 687854',
    BUSINESS_WHATSAPP: 'https://wa.me/447495687854'
}, (typeof window !== 'undefined' && window.LPDM_CONFIG) || {}));


/* =====================================================================
   2. NAVIGATION (Mobile Menu Toggle + Outside-Click Close)
   ===================================================================== */
function initNavigation() {
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    if (!hamburger || !navMenu) return;

    const closeMenu = () => {
        hamburger.classList.remove('active');
        navMenu.classList.remove('active');
    };

    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('active');
        navMenu.classList.toggle('active');
    });

    // Keyboard accessibility for hamburger
    hamburger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            hamburger.click();
        }
    });

    // Close menu when clicking a nav link
    navMenu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', closeMenu);
    });

    // Close menu when clicking outside
    document.addEventListener('click', (event) => {
        if (!navMenu.classList.contains('active')) return;
        const insideNav = navMenu.contains(event.target);
        const onHamburger = hamburger.contains(event.target);
        if (!insideNav && !onHamburger) closeMenu();
    });
}


/* =====================================================================
   3. SMOOTH SCROLLING (in-page anchor links only)
   ===================================================================== */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#' || href === '') return;
            const target = document.querySelector(href);
            if (!target) return;
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
}


/* =====================================================================
   4. STICKY NAV SHADOW ON SCROLL
   ===================================================================== */
function initNavScrollEffect() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    const onScroll = () => {
        navbar.style.boxShadow = window.scrollY > 50
            ? '0 4px 20px rgba(0, 0, 0, 0.15)'
            : '0 2px 10px rgba(0, 0, 0, 0.1)';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
}


/* =====================================================================
   5. SCROLL-IN ANIMATIONS (cards, features, testimonials)
   ===================================================================== */
function initScrollAnimations() {
    const animatedElements = document.querySelectorAll(
        '.service-card, .feature-item, .testimonial-card'
    );
    if (!animatedElements.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    animatedElements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = `all 0.6s ease ${index * 0.1}s`;
        observer.observe(el);
    });
}


/* =====================================================================
   6. CONTACT ANALYTICS HOOKS (phone / WhatsApp clicks)
   ===================================================================== */
function initContactAnalytics() {
    document.querySelectorAll('a[href^="tel:"]').forEach((link) => {
        link.addEventListener('click', () => {
            console.log('[analytics] phone_call', link.getAttribute('href'));
            // Backend team: wire to gtag / GA4 here
            // gtag('event', 'phone_call', { event_category: 'contact' });
        });
    });

    document.querySelectorAll('a[href^="https://wa.me"]').forEach((link) => {
        link.addEventListener('click', () => {
            console.log('[analytics] whatsapp_click');
            // gtag('event', 'whatsapp_click', { event_category: 'contact' });
        });
    });
}


/* =====================================================================
   7. SCROLL-TO-TOP BUTTON
   ===================================================================== */
function initScrollToTop() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Scroll to top');
    btn.innerHTML = '<i class="fas fa-arrow-up"></i>';
    btn.className = 'scroll-to-top';
    btn.style.cssText = `
        position: fixed;
        bottom: 100px;
        right: 30px;
        width: 50px;
        height: 50px;
        background-color: #2E75B6;
        color: white;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s;
        z-index: 998;
        font-size: 20px;
    `;
    document.body.appendChild(btn);

    window.addEventListener('scroll', () => {
        const visible = window.scrollY > 500;
        btn.style.opacity = visible ? '1' : '0';
        btn.style.visibility = visible ? 'visible' : 'hidden';
    }, { passive: true });

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}


/* =====================================================================
   8. ACTIVE NAV LINK (based on current page filename)
   ===================================================================== */
function initActiveNavLink() {
    const current = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-menu a').forEach((link) => {
        const href = link.getAttribute('href');
        if (href === current) link.classList.add('active');
    });
}


/* =====================================================================
   9. LAZY-LOADED IMAGES (img[data-src])
   ---------------------------------------------------------------------
   Note: native loading="lazy" is preferred and used in markup. This
   handles legacy data-src patterns if the backend ever emits them.
   ===================================================================== */
function initLazyImages() {
    const images = document.querySelectorAll('img[data-src]');
    if (!images.length) return;

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const img = entry.target;
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
            obs.unobserve(img);
        });
    });
    images.forEach((img) => observer.observe(img));
}


/* =====================================================================
   10. VALIDATION HELPERS
   ===================================================================== */
const Validators = {
    email(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    },
    phone(value) {
        if (!/^[\d\s+\-()]+$/.test(value)) return false;
        return value.replace(/\D/g, '').length >= 10;
    },
    nonEmpty(value) {
        return typeof value === 'string' && value.trim().length > 0;
    }
};


/* =====================================================================
   11. QUOTE FORM CONTROLLER
   ---------------------------------------------------------------------
   Auto-binds to any <form data-form="quote"> on the page.
   Contract with backend (Flask):

     POST {API_QUOTE_ENDPOINT}
     Headers: { "Content-Type": "application/json", "Accept": "application/json" }
     Body: {
       name: string,
       email: string,
       phone: string,
       service: string,
       property_size: string | null,
       message: string | null,
       source: "website",
       submitted_at: ISO-8601 string
     }

   Expected success: HTTP 2xx with optional JSON { id, status }.
   Anything else (network error, 4xx, 5xx, timeout) → fallback banner.
   ===================================================================== */
function initQuoteForms() {
    const forms = document.querySelectorAll('form[data-form="quote"]');
    forms.forEach((form) => new QuoteFormController(form));
}

class QuoteFormController {
    constructor(formEl) {
        this.form = formEl;
        this.submitBtn = formEl.querySelector('[data-form-submit]');
        this.submitLabel = formEl.querySelector('[data-submit-label]');
        this.submitSpinner = formEl.querySelector('[data-submit-spinner]');

        // Banners live as siblings inside the form's wrapper
        const wrapper = formEl.closest('.quote-form-wrapper') || formEl.parentElement;
        this.errorBanner = wrapper.querySelector('[data-form-message="error"]');
        this.successBanner = wrapper.querySelector('[data-form-message="success"]');

        this.form.addEventListener('submit', (e) => this.onSubmit(e));
    }

    async onSubmit(event) {
        event.preventDefault();
        this.hideBanners();

        const payload = this.collectPayload();
        const errors = this.validate(payload);
        if (errors.length) {
            this.markInvalid(errors);
            return;
        }

        this.setPending(true);

        try {
            const response = await this.postWithTimeout(
                CONFIG.API_QUOTE_ENDPOINT,
                payload,
                CONFIG.REQUEST_TIMEOUT_MS
            );

            if (!response.ok) {
                throw new Error(`API returned HTTP ${response.status}`);
            }

            // Best-effort response body parse — not required for success UX
            try { await response.json(); } catch (_) { /* non-JSON OK */ }

            this.handleSuccess();
        } catch (err) {
            console.error('[QuoteForm] submission failed:', err);
            this.handleFailure();
        } finally {
            this.setPending(false);
        }
    }

    collectPayload() {
        const fd = new FormData(this.form);
        return {
            name: (fd.get('name') || '').toString().trim(),
            email: (fd.get('email') || '').toString().trim(),
            phone: (fd.get('phone') || '').toString().trim(),
            service: (fd.get('service') || '').toString().trim(),
            property_size: (fd.get('property_size') || '').toString().trim() || null,
            message: (fd.get('message') || '').toString().trim() || null,
            preferred_date: (fd.get('preferred_date') || '').toString().trim() || null,
            referral_source: (fd.get('referral_source') || '').toString().trim() || null,
            source: 'website',
            submitted_at: new Date().toISOString()
        };
    }

    validate(payload) {
        const errors = [];
        if (!Validators.nonEmpty(payload.name)) errors.push('name');
        if (!Validators.email(payload.email)) errors.push('email');
        if (!Validators.phone(payload.phone)) errors.push('phone');
        if (!Validators.nonEmpty(payload.service)) errors.push('service');
        return errors;
    }

    markInvalid(fieldNames) {
        // Reset all aria-invalid first
        this.form.querySelectorAll('[aria-invalid]').forEach((el) => {
            el.removeAttribute('aria-invalid');
        });
        fieldNames.forEach((name) => {
            const field = this.form.querySelector(`[name="${name}"]`);
            if (field) {
                field.setAttribute('aria-invalid', 'true');
            }
        });
        // Focus the first invalid field for accessibility
        const first = this.form.querySelector(`[name="${fieldNames[0]}"]`);
        if (first) first.focus();
    }

    setPending(isPending) {
        if (!this.submitBtn) return;
        this.submitBtn.disabled = isPending;
        this.submitBtn.classList.toggle('is-loading', isPending);
        this.submitBtn.setAttribute('aria-busy', isPending ? 'true' : 'false');

        if (this.submitLabel && this.submitSpinner) {
            this.submitLabel.hidden = isPending;
            this.submitSpinner.hidden = !isPending;
        }
    }

    postWithTimeout(url, body, timeoutMs) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);

        return fetch(url, {
            method: 'POST',
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(body),
            signal: controller.signal
        }).finally(() => clearTimeout(timer));
    }

    handleSuccess() {
        if (this.successBanner) {
            this.successBanner.hidden = false;
            this.scrollIntoView(this.successBanner);
        }
        this.form.reset();
    }

    handleFailure() {
        if (this.errorBanner) {
            this.errorBanner.hidden = false;
            this.scrollIntoView(this.errorBanner);
        }
    }

    hideBanners() {
        if (this.errorBanner) this.errorBanner.hidden = true;
        if (this.successBanner) this.successBanner.hidden = true;
    }

    scrollIntoView(el) {
        try {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (_) { /* older browsers — ignore */ }
    }
}


/* =====================================================================
   12. HERO CAROUSEL (homepage)
   ===================================================================== */
function initHeroCarousel() {
    const track = document.querySelector('.carousel-track');
    if (!track) return;

    const slides = Array.from(track.querySelectorAll('.carousel-slide'));
    const dots   = Array.from(document.querySelectorAll('.carousel-nav__dot'));
    const prev   = document.querySelector('.carousel-arrow--prev');
    const next   = document.querySelector('.carousel-arrow--next');

    let current = 0;
    let timer;

    function goTo(index) {
        slides[current].classList.remove('is-active');
        if (dots[current]) dots[current].classList.remove('is-active');
        current = (index + slides.length) % slides.length;
        slides[current].classList.add('is-active');
        if (dots[current]) dots[current].classList.add('is-active');
    }

    function resetTimer() {
        clearInterval(timer);
        timer = setInterval(() => goTo(current + 1), 5000);
    }

    dots.forEach((dot, i) => dot.addEventListener('click', () => { goTo(i); resetTimer(); }));
    if (prev) prev.addEventListener('click', () => { goTo(current - 1); resetTimer(); });
    if (next) next.addEventListener('click', () => { goTo(current + 1); resetTimer(); });

    resetTimer();
}

/* =====================================================================
   13. BOOTSTRAP — single DOMContentLoaded entry point
   ===================================================================== */
document.addEventListener('DOMContentLoaded', () => {
    // Set minimum date on any preferred_date input to today
    const dateInput = document.querySelector('input[name="preferred_date"]');
    if (dateInput) {
        dateInput.min = new Date().toISOString().split('T')[0];
    }

    initHeroCarousel();
    initNavigation();
    initSmoothScroll();
    initNavScrollEffect();
    initScrollAnimations();
    initContactAnalytics();
    initScrollToTop();
    initActiveNavLink();
    initLazyImages();
    initQuoteForms();

    console.log(
        '%cLPD&M Cleaning Solutions',
        'color: #2E75B6; font-size: 24px; font-weight: bold;'
    );
    console.log(
        '%cProfessional Cleaning Services in Enfield & North London',
        'color: #70AD47; font-size: 14px;'
    );
});
