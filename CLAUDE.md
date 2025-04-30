# Claude Code Reference Guide for Unsubscriber

This document provides helpful information for Claude Code to assist with this project.

## Project Overview

Unsubscriber is a web application that helps users:
- Scan Gmail inbox for subscription emails
- Extract unsubscribe links automatically
- Batch process unsubscribe requests
- Optionally archive emails (requires additional permissions)

## Project Structure

- `/api/` - Backend Flask Python code
  - `auth.py` - Authentication with Google OAuth
  - `config.py` - Configuration settings
  - `index.py` - Main application routes and setup
  - `scan.py` - Email scanning and unsubscribe functionality
  - `utils.py` - Utility functions for credentials and API

- `/templates/` - Frontend Jinja templates
  - `base.html` - Base template with common layout
  - `index.html` - Homepage
  - `scan_results.html` - Results of email scanning
  - `privacy.html` - Privacy policy
  - `oauth2callback.html` - Intermediate page for OAuth handling

- `/public/` - Static assets
  - `/static/` - CSS, JS, images
  - `/images/` - Application images

## UI Design Guidelines

The application follows a modern, minimalist design system inspired by ShadCN, Radix, and Linear interfaces. 

### Design System

#### Color System
- **HSL Color Model**: All colors use HSL format with optional opacity values (e.g., `hsl(var(--brand))`)
- **Brand Color**: Blue (`--brand: 221.2 83.2% 53.3%`) serves as the primary accent
- **Success Color**: Green (`--success: 142.1 76.2% 36.3%`) for success states
- **Destructive Color**: Red (`--destructive: 0 84.2% 60.2%`) for errors/warnings
- **Light/Dark Modes**: Full theme support with appropriate contrast ratios

#### Typography
- **Font Family**: Inter (with system fallbacks)
- **Font Weights**: Regular (400), Medium (500), Semibold (600), Bold (700)
- **Text Colors**: Primary text, muted text, and action text variants
- **Header Hierarchy**: Clear scaling from h1 to h6

#### Components

##### Buttons
- **Variants**: Primary, Secondary, Brand, Destructive, Outline, Ghost
- **Sizes**: Small, Medium, Large
- **States**: Default, Hover, Loading, Disabled
- **Animations**: Subtle hover and loading states

##### Cards
- **Styling**: Rounded corners, subtle borders, and shadows
- **Background**: Solid background with full opacity
- **Variants**: Default cards, feature cards with accents, content cards

##### Alerts/Notifications
- **Positioning**: Top-right floating notifications
- **Animation**: Fade-in, auto-dismiss after 6 seconds
- **Variants**: Success, Error, Warning, Info
- **Design**: Icon, message text, and optional close button

##### Form Controls
- **Input Fields**: Consistent styling with focus states
- **Checkboxes/Toggles**: Custom styled controls
- **Validation**: Clear error state styling

#### Layout Patterns

##### Hero Section
- **Design**: Split layout with content on left, illustration on right
- **Animation**: Subtle fade-in-up and staggered animations
- **Background**: Subtle gradients and floating blurred elements
- **Grid Pattern**: Understated background pattern

##### Features Grid
- **Layout**: 3-column responsive grid
- **Content**: Icon/title/description format
- **Styling**: Soft background with brand accent elements

##### Navigation
- **Position**: Sticky top navigation with brand identity
- **Styling**: Subtle border and shadow separation
- **Controls**: Theme toggle and authentication actions

##### Footer
- **Layout**: Two-column with branding and links
- **Content**: Brand attribution, privacy links, source code link
- **Styling**: Subtle top border with appropriate spacing

#### Animation Guidelines

- **Entrance Animations**: Fade-in-up for content sections
- **Interaction Feedback**: Subtle scale or translation effects
- **Loading States**: Custom spinner with brand colors
- **Transitions**: Smooth transitions between states (300-600ms)

#### Responsive Design

- **Breakpoints**: Mobile (<768px), Tablet (768px-1024px), Desktop (>1024px)
- **Layout Shifts**: Column stacking on mobile, side-by-side on larger screens
- **Touch Targets**: Minimum 44px for interactive elements
- **Typography**: Fluid scaling for comfortable reading at all sizes

### Implementation Details

- **CSS Variables**: Design tokens stored as CSS variables for consistency
- **HSL Color Model**: All colors use HSL for easy manipulation
- **Utility Classes**: Consistent naming for background, text, border properties
- **Tailwind CSS**: Primary styling framework with custom extensions
- **!important**: Used selectively to ensure full opacity backgrounds

### Animation Examples

```css
/* Fade-in-up animation */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Floating animation */
@keyframes float {
    0% { transform: translateY(0px) rotate(1deg); }
    50% { transform: translateY(-8px) rotate(-0.5deg); }
    100% { transform: translateY(0px) rotate(1deg); }
}

/* Pulse animation */
@keyframes pulse {
    0% { transform: scale(0.8); opacity: 0.8; }
    50% { transform: scale(1.2); opacity: 1; }
    100% { transform: scale(0.8); opacity: 0.8; }
}
```

## Key Configuration 

- Default scope: `gmail.readonly` (minimal permissions)
- Optional scope: `gmail.modify` (for archiving functionality)
- OAuth is handled via Flask-Session with pickled credentials

## Important Functionality

### Permission Model

1. **Default Read-Only Access**:
   - Application starts with minimal `gmail.readonly` scope
   - Can scan emails and extract unsubscribe links
   - Cannot archive emails

2. **Optional Archive Permission**:
   - Users can upgrade to `gmail.modify` scope
   - Permission request shows clear explanation modal
   - Archive checkbox becomes enabled with permissions
   - Archive functionality moves emails out of inbox

### Authentication Flow

1. User clicks login or "Enable archiving"
2. OAuth request made with appropriate scope
3. User authorizes in Google
4. Redirect to `/oauth2callback` intermediate page (to prevent loops)
5. Auth callback processes token with proper handling for scope changes
6. Credentials stored in session

### Email Scanning Process

1. User clicks "Scan Inbox"
2. Backend queries Gmail API using search terms optimized for subscription emails
3. Unsubscribe links extracted from email headers
4. Results grouped by sender
5. User can select emails to process

### Unsubscribe Flow

1. User selects emails (max 25 at once)
2. Clicks "Unsubscribe" button
3. Processing:
   - HTTP links handled client-side when possible
   - Mailto links shown to user
   - Manual intervention links provided when needed
4. Optional archiving if permissions granted

## Common Tasks and Commands

### Development

To run the application locally:
```bash
python api/index.py --debug
```

Or using Vercel CLI:
```bash
vercel dev --listen 127.0.0.1:5001
```

### Checking Permissions

To check if a user has archive permissions:
```python
utils.has_modify_scope()  # Returns True/False
```

### Debugging Authentication Issues

- Check the access token scope: `creds.scopes`
- Check if credentials exist and are valid: `creds.valid`
- Inspect OAuth flow for correct redirect URI

## Known Issues and Solutions

1. **OAuth Scope Change Loop**:
   - Problem: When changing permissions from readonly to modify, redirect can loop or error with "Scope has changed" message
   - Solution: 
     1. Created a custom `NoScopeValidationFlow` class that extends the standard Google OAuth flow but skips scope validation
     2. When upgrading, request both scopes at once: `['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.readonly']`
     3. Preserve `oauth_state` in session during intermediate redirect (only clear credentials)
     4. Use traditional redirects that maintain session cookies properly

2. **Session Storage Limitations**:
   - Problem: Vercel functions are stateless, requiring session pickle storage
   - Solution: Session state maintained through Flask-Session

3. **Gmail API Rate Limits**:
   - Problem: Too many requests can hit rate limits
   - Solution: Batch processing, caching, and limiting to 25 emails at once

## UI Components

- Modal system for feedback and permissions
- Progress tracking for batch operations
- Email selection tracking across pages using sessionStorage

## Testing Tips

- Use different permission states to verify UI adapts correctly
- Check handling of various unsubscribe link types (http, mailto, etc.)
- Verify error handling when permissions change