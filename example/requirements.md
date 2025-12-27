# AuthFlow - Example Project

A simple authentication system to practice the LeanVibes backlog workflow.

## Project Overview

Build a basic user authentication system with signup and login pages. This is a fake project designed to help you practice the backlog workflow with realistic tasks.

## Core Requirements

### 1. Signup Page
- Email input field
- Password input field (min 8 characters)
- Confirm password field
- "Create Account" button
- Link to login page

### 2. Login Page
- Email input field
- Password input field
- "Sign In" button
- Link to signup page
- "Forgot Password" link

### 3. Basic Validation
- Email format validation
- Password minimum length
- Password confirmation match

---

## Try the Workflow

Use this project to practice LeanVibes. Here's a suggested walkthrough:

### Step 1: Add Initial Tasks to Backlog

Try adding these as backlog items:

```
/backlog-add high feature Create signup page with form fields
/backlog-add high feature Create login page with form fields
/backlog-add medium feature Add form validation
/backlog-add low enhancement Add "Remember me" checkbox
/backlog-add low enhancement Add password strength indicator
/backlog-add low debt Add unit tests for validation logic
```

### Step 2: View Your Backlog

```
/backlog
```

You should see items organized by priority.

### Step 3: Work on an Item

```
/backlog 1
```

This loads issue #1 and reminds you that commits will include `Fixes #1`.

### Step 4: Experience Proactive Suggestions

While working, if you mention something like:

> "We should also add social login with Google..."

The AI should suggest deferring it to the backlog since it's not part of the core requirements.

### Step 5: Commit with Issue Reference

When you commit, it should include:

```
Add signup page with email and password fields

Fixes #1
```

---

## Stretch Goals (Perfect for Backlog Practice)

These are intentionally "nice to have" features. When discussed during implementation, they should trigger backlog suggestions:

- Social login (Google, GitHub)
- Two-factor authentication
- Password reset flow
- Remember me functionality
- Account lockout after failed attempts
- Email verification
- Password strength meter
- Accessibility improvements (ARIA labels)
- Dark mode for auth pages
- Rate limiting on login attempts

---

## Notes

This is a fake project - you don't need to actually build anything! The goal is to practice:

1. Adding items to the backlog
2. Working on items from the backlog
3. Seeing proactive suggestions when scope creeps
4. Committing with proper issue references
5. Watching issues auto-close

Feel free to modify this requirements file or create your own project to practice with.
