# Quality Thought Website Test Plan

## Application Overview

Plan for validating the public Quality Thought website (https://qualitythought.in), including homepage content, course discovery, navigation and learning-journey components, promotional registration prompts, reviews, contact channels, the learning portal, and footer resources. All scenarios start from a fresh browser context with no prior site data or authentication. Use non-production test details only; do not complete purchases, make real calls, send real messages, or submit sensitive personal information. A scenario passes only when every stated expected result is met; missing, incorrect, inaccessible, or broken UI/navigation is a failure.

## Test Scenarios

### 1. Homepage and Course Discovery

**Seed:** `tests/seed.spec.ts`

#### 1.1. Render the homepage and dismiss the scholarship promotion

**File:** `tests/homepage/homepage-render-and-promotions.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to https://qualitythought.in/.
    - expect: The homepage loads over HTTPS and shows the Quality Thought page title and logo.
    - expect: The primary hero heading, supporting description, and Join a Free Master Class action are visible.
    - expect: The scholarship promotion, when displayed, identifies the free scholarship test, delivery mode, scheduled date/time, covered course categories, and Attend Scholarship Test and No thanks actions.
  2. Choose No thanks on the scholarship promotion.
    - expect: The promotion closes without navigating away from the homepage.
    - expect: The main page remains usable, and the promotion does not immediately reopen during the same session.
  3. Reload the homepage.
    - expect: The page renders without a broken layout or blocking error; promotion display follows its configured dismissal behavior.

#### 1.2. Navigate the global menu and its category submenus

**File:** `tests/homepage/global-navigation.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and inspect the Global Menu.
    - expect: The Courses, Upcoming Batches, Resources, Our Entities, Branches, and More categories are available in the global navigation.
  2. Open each category using its menu button, then inspect and select a representative submenu destination.
    - expect: Each category opens its corresponding submenu and exposes usable, correctly labeled destinations.
    - expect: Selecting a destination loads the corresponding page or section without a broken link; browser Back returns to the expected prior page.
  3. Repeat menu interaction using keyboard focus and Enter or Space, and close an open menu with Escape where supported.
    - expect: Menu controls are keyboard reachable and activation/closing behavior is consistent with the menu UI.

#### 1.3. Browse trending and featured courses

**File:** `tests/homepage/course-discovery.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and locate Trending Courses and Featured Courses.
    - expect: Both course sections render with their headings and course cards.
    - expect: Each visible card presents its course identity and a usable View Course Details action where applicable.
  2. Open View Course Details for one featured course.
    - expect: The selected course's details page opens and identifies the same course.
    - expect: The destination provides a clear way to return to the homepage or previous page.
  3. Use browser Back, then open a course from Trending Courses if a details action is available.
    - expect: The homepage and course cards remain usable after returning; the selected trending course destination matches its card.

#### 1.4. Switch between learning journey tabs

**File:** `tests/homepage/learning-journey-tabs.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and locate Choose Your Learning Journey.
    - expect: The Professional Upskilling, Placement Bootcamps, Skill To Job, and Corporate Training tabs are visible.
    - expect: Professional Upskilling is selected initially and an associated tab panel is present.
  2. Select each tab in turn.
    - expect: The selected state moves to the chosen tab and the corresponding tab panel is displayed.
    - expect: Switching tabs does not navigate away or leave multiple tabs marked selected.
  3. Use keyboard arrow keys to move between tabs and Enter or Space to activate a tab.
    - expect: Tab navigation and activation work from the keyboard, with focus and selected state remaining understandable.

#### 1.5. Operate student review pagination and image carousels

**File:** `tests/homepage/reviews-and-carousels.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and locate What Our Students Say On Google.
    - expect: The review section displays its heading, review content, Previous and Next controls, and page navigation where provided.
  2. Select Next, Previous, and a non-current page number.
    - expect: Review content changes to the selected page, controls remain enabled or disabled appropriately at boundaries, and the selected page is identified.
  3. Locate each Image Carousel on the homepage and use its available navigation controls.
    - expect: Carousel content advances and can be navigated back without layout breakage or loss of page usability.

### 2. Registration, Contact, and Site Resources

**Seed:** `tests/seed.spec.ts`

#### 2.1. Open and validate the free master class registration prompt

**File:** `tests/registration/free-master-class.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and activate Join a Free Master Class.
    - expect: A registration popup or page opens without navigating to an unrelated destination.
    - expect: The registration interface exposes its purpose and all required fields and actions, if registration is offered in the popup.
  2. If a form is presented, submit it empty, then enter malformed email and phone values and submit again.
    - expect: Required fields and invalid values are identified with clear validation feedback.
    - expect: Invalid submissions are not accepted and entered values remain available for correction.
  3. Enter valid synthetic test details and submit only if the site offers a non-binding registration flow.
    - expect: A clear success or next-step confirmation is shown and duplicate submissions are prevented while processing.
    - expect: No unexpected purchase, payment, or external communication is triggered.
  4. Close the popup using its close control and reopen it from the hero action.
    - expect: The popup closes and can be opened again; dismissal does not leave a blocking overlay behind.

#### 2.2. Review and follow the scholarship test promotion

**File:** `tests/registration/scholarship-test-promotion.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and wait for the scholarship promotion to appear, if configured.
    - expect: The promotion clearly shows the test title, delivery options, scheduled date and time, covered courses, and an Attend Scholarship Test action.
  2. Activate Attend Scholarship Test and inspect the destination without entering or submitting personal information.
    - expect: The link opens the scholarship test destination over a secure connection or provides an understandable unavailable-state message.
    - expect: The destination corresponds to the advertised scholarship test.
  3. Return to the homepage and dismiss the promotion with No thanks.
    - expect: The promotion closes, the homepage remains usable, and no registration is submitted.

#### 2.3. Verify expert contact options and floating chat entry

**File:** `tests/contact/contact-options.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage and locate Talk to Our Experts and the floating Chat now control.
    - expect: The expert contact section identifies available contact methods, including chat, call, email, and booking where offered.
    - expect: The floating chat control is visible and does not obstruct essential page controls.
  2. Activate each contact action and inspect the link destination or resulting interface without sending a real message or placing a call.
    - expect: Call, email, chat, and booking actions resolve to the correctly typed destination or open their expected interface.
    - expect: Each action is labeled clearly; returning to the site remains possible.
  3. Open and close the floating chat interface without submitting a message.
    - expect: The chat panel opens and can be dismissed; no message is sent without explicit submission.

#### 2.4. Verify learning portal and footer resources

**File:** `tests/resources/lms-and-footer-links.spec.ts`

**Steps:**
  1. In a fresh browser context, navigate to the homepage, scroll to the Learning Portal section, and activate Login to LMS.
    - expect: The link opens https://learn.qualitythought.in/ or an understandable unavailable-state message.
    - expect: The destination is identified as the Quality Thought learning portal; no credentials are submitted.
  2. Return to the homepage and inspect footer links for FAQs, Cancellation & Refunds, Privacy Policy, Terms & Conditions, View Disclaimer, and the profile download.
    - expect: Each listed resource link is present, labeled, and opens the corresponding page or document.
    - expect: The brochure/profile link opens a readable document or downloads a valid file; browser Back returns to the homepage.
  3. Open footer social links without posting or signing in.
    - expect: Each social link opens its labeled platform destination and does not unexpectedly redirect to an unrelated site.
