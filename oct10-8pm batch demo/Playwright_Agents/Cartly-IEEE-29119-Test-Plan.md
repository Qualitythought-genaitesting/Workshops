# Cartly Web Application System Test Plan (IEEE 29119-aligned)

## Application Overview

# Plan basis and control

**Purpose:** Provide a risk-based, repeatable system test plan for the public Cartly shopping-preview web application at https://aisle-and-smile.lovable.app.

**Standards alignment:** Structured with reference to ISO/IEC/IEEE 29119-1:2022 (concepts and definitions), ISO/IEC/IEEE 29119-2:2021 (test processes), ISO/IEC/IEEE 29119-3:2021 (test documentation), and ISO/IEC/IEEE 29119-4:2021 (test techniques). This is an IEEE/ISO standards-aligned working plan, not a declaration of certification or full conformance. Apply risk-based test design, explicit expected results, independent cases, recorded evidence, and traceability from each scenario to a user-visible feature. Verify the applicable edition against the organization’s standards subscription before making a formal compliance claim.

**System under test:** Cartly — Everyday favourites, extraordinary finds. The observed UI contains a landing page and featured-offer carousel; categories (All categories, Electronics, Mobiles, Fashion, Home & Living, Appliances, Beauty & More); searchable and sortable product listings; product detail dialogs; wishlist add/remove and count; collection content; and a footer. The site identifies itself as a sample collection/shopping preview, and product details state that live purchasing is unavailable.

**Objectives:** Verify core browse-to-discover workflows; accurate filtering, sorting, product details, and wishlist state; useful empty states and recovery; keyboard/screen-reader usability; responsive rendering; and graceful behavior under common browser/network variations.

**Scope:** Public, unauthenticated browser UI and its visible client-side interactions. No account registration, payment, order placement, backend administration, or checkout flow was observed; treat those as out of scope unless product requirements establish otherwise. Do not use real personal or payment data.

**Approach and test design:** Black-box functional tests, equivalence partitioning (matching/no-match queries, populated/empty categories), boundary-oriented input checks, state-transition tests (save/remove/modal close), comparative order checks for sort options, and manual accessibility/responsive/compatibility checks. Use a clean browser context and blank wishlist at the start of every case unless a case explicitly builds state within that test. Keep scenarios independent and restore the initial state afterward.

**Environment:** Record test date/time, browser and exact version, operating system, viewport, device emulation, network profile, and build/deployment identifier with each run. Minimum browser matrix: current stable Chromium, Firefox, and WebKit/Safari where available; desktop and mobile-sized viewports. Run with normal network and at least one throttled/poor-network profile. Clear site storage and cookies before each independent case. Use only the public sample catalog.

**Entry criteria:** Target URL is reachable over HTTPS; deployed build is identified; test browser is available; and the tester has the current product requirements, including expected catalog membership, sorting tie rules, wishlist persistence, and supported viewport/browser matrix where defined.

**Exit criteria:** All critical browse, detail, and wishlist cases pass; all test cases have pass/fail/blocked status and reproducible evidence; no open severity-1 or severity-2 defect remains without an approved risk waiver; and failures, environment details, and unresolved requirement questions are documented. Report coverage as executed cases divided by planned cases, with failures and blockers explicitly listed.

**Pass/fail and evidence:** A case passes only when each stated expected result is met. Capture reproducible steps, sanitized screenshots or accessibility snapshots, console/network error summaries, and the environment for failures; do not include credentials or personal data. Distinguish a product defect from an unresolved requirement. Confirm exact inventory and persistence expectations with the product owner rather than treating assumptions as requirements.

**Key risks and assumptions:** This is a preview with sample data; inventory may intentionally be sparse (Mobiles showed an empty state during reconnaissance), and the UI states that purchasing is unavailable. Product counts and text may change. Wishlist persistence across reloads/devices and carousel autoplay/wrap behavior were not established and must be confirmed. Images depend on network availability. The Lovable edit badge is third-party authoring chrome, not a shopping feature.

**Accessibility reference:** Include manual and automated checks informed by WCAG 2.2 AA for keyboard operation, focus visibility/order, names/roles/states, contrast, zoom/reflow, and image alternatives. Record the tool and version for automated scans; automated results do not replace manual checks.

## Test Scenarios

### 1. S1 — Landing page, navigation, and catalog categories

**Seed:** `tests/seed.spec.ts`

#### 1.1. TC-001 — Load landing page and verify primary content

**File:** `tests/cartly/landing-page.spec.ts`

**Steps:**
  1. Start from a clean browser context and navigate to the application root URL.
    - expect: The HTTPS page loads without a blocking error and has the Cartly page title/branding.
  2. Inspect the header, primary category navigation, main content, and footer using the accessibility tree.
    - expect: A clearly named product search textbox and Wishlist control are available.
    - expect: Category navigation exposes All categories and the six observed categories.
    - expect: The home page exposes a Featured offers region, product content, collection content, and footer.
    - expect: Images with meaningful content have useful alternative text; decorative images do not create confusing accessible names.
  3. Check the initial catalog and featured content after page loading settles.
    - expect: Featured product cards and offer content render without overlapping or stale loading placeholders.
    - expect: No uncaught page error or blocking resource failure prevents core browsing.

#### 1.2. TC-002 — Filter catalog by a populated category and return to all categories

**File:** `tests/cartly/category-filter.spec.ts`

**Steps:**
  1. Start with a clean browser context, navigate to the root URL, and note the initially visible catalog products.
    - expect: The landing page and initial catalog are available.
  2. Activate Electronics in the Product categories navigation.
    - expect: Electronics becomes the selected/pressed category.
    - expect: The listing heading identifies Electronics and reports the visible product count.
    - expect: Only products assigned to Electronics are shown; the observed sample contains three products.
  3. Activate All categories.
    - expect: All categories becomes selected.
    - expect: The unfiltered landing/catalog content is restored, including products from multiple represented categories.

#### 1.3. TC-003 — Show empty-category state and recover to all products

**File:** `tests/cartly/empty-category-recovery.spec.ts`

**Steps:**
  1. Start from a clean browser context and open the root URL.
    - expect: The page is ready for category interaction.
  2. Select Mobiles, which showed no products during reconnaissance.
    - expect: Mobiles is visibly selected and its listing reports zero products when the deployed sample inventory remains unchanged.
    - expect: A clear No products found state and recovery action are displayed rather than a blank or broken page.
  3. Activate Browse all products from the empty state.
    - expect: The empty state is dismissed and the all-products view returns with products visible.
    - expect: The category selection and result count are consistent with the restored view.

#### 1.4. TC-004 — Verify each remaining category has a consistent result state

**File:** `tests/cartly/category-smoke.spec.ts`

**Steps:**
  1. Start from a clean browser context and open the root URL.
    - expect: Category navigation is available.
  2. Select Fashion, Home & Living, Appliances, and Beauty & More one at a time; record heading, count, visible products, and empty-state message for each.
    - expect: Each control updates the selected state and listing without a page error.
    - expect: Displayed products belong to the selected category; if a category has no inventory, it shows the same usable empty state and browse-all recovery affordance.
    - expect: Counts agree with the rendered product cards.

#### 1.5. TC-005 — Navigate featured offers and use the offer call to action

**File:** `tests/cartly/featured-offers.spec.ts`

**Steps:**
  1. Start from a clean browser context and open the root URL.
    - expect: The Featured offers region exposes Previous offer, Next offer, and Explore deals controls with accessible names.
  2. Activate Next offer, then Previous offer.
    - expect: Each action changes the active offer content or indicator as applicable.
    - expect: The controls remain operable and the active slide is exposed accessibly; no assumption is made about wraparound unless specified by product requirements.
  3. Activate Explore deals on the active offer.
    - expect: The action takes the user to a relevant product/deals area or otherwise performs the documented offer action.
    - expect: The resulting content is reachable by keyboard and does not leave the user at an unrelated or empty section.

### 2. S2 — Product search, empty results, and sorting

**Seed:** `tests/seed.spec.ts`

#### 2.1. TC-006 — Find a product using a partial matching search term

**File:** `tests/cartly/search-match.spec.ts`

**Steps:**
  1. Start from a clean browser context and navigate to the root URL.
    - expect: The Search products textbox is available.
  2. Enter headphones in Search products.
    - expect: The result heading reflects the query and one matching SoundWave Pro Wireless Headphones product is shown in the observed catalog.
    - expect: The result count agrees with the visible card count and irrelevant cards are absent.
  3. Replace the query with a case variation and a distinctive partial brand or product term.
    - expect: Matching behavior is consistent with the catalog’s intended search rules and does not produce duplicate cards.

#### 2.2. TC-007 — Handle a search with no matching products

**File:** `tests/cartly/search-no-results.spec.ts`

**Steps:**
  1. Start from a clean browser context and open the root URL.
    - expect: The product search control is ready.
  2. Search for a unique non-matching term such as zz-no-match-123.
    - expect: The query is reflected in the results heading, zero products are reported, and a No products found message is displayed.
    - expect: The empty result has an understandable suggestion and a Browse all products recovery action.
  3. Activate Browse all products, then use Clear search if available.
    - expect: The user can return to a populated unfiltered catalog without reloading or becoming trapped in the empty state.
    - expect: The search field and listing state are synchronized.

#### 2.3. TC-008 — Clear a matching query and restore results

**File:** `tests/cartly/search-clear.spec.ts`

**Steps:**
  1. Start from a clean browser context and search for headphones.
    - expect: The matching product result appears and a Clear search control is exposed.
  2. Activate Clear search.
    - expect: The textbox is emptied and the unfiltered catalog is restored.
    - expect: The result heading, count, selected category, and rendered cards no longer reflect stale search results.

#### 2.4. TC-009 — Handle whitespace, punctuation, and repeated search edits

**File:** `tests/cartly/search-input-boundaries.spec.ts`

**Steps:**
  1. Start from a clean browser context and enter a matching term with leading/trailing spaces, then enter a query containing ordinary punctuation such as ampersands or apostrophes.
    - expect: The application remains responsive and renders a deterministic result or empty state without treating punctuation as markup or breaking layout.
    - expect: Whitespace normalization and punctuation matching follow documented product requirements; record behavior if requirements are absent.
  2. Edit the same query repeatedly, including clearing and re-entering a term.
    - expect: Results update to the current input and do not retain stale cards or counts.
    - expect: No duplicate result cards or console-breaking errors appear.

#### 2.5. TC-010 — Sort a populated category using every supported sort option

**File:** `tests/cartly/sort-order.spec.ts`

**Steps:**
  1. Start from a clean browser context and select Electronics.
    - expect: Three sample Electronics products and the Sort products combobox are available, subject to inventory remaining unchanged.
  2. Select Price: low to high and compare the displayed numeric prices from first to last.
    - expect: Products are in non-decreasing numeric price order; currency symbols and thousands separators do not affect comparison.
  3. Select Price: high to low, Top rated, and Featured in turn.
    - expect: Price descending is non-increasing; Top rated follows numeric rating order; Featured restores the documented default sequence.
    - expect: The option shown as selected matches the actual list order and all expected products remain present.

#### 2.6. TC-011 — Combine category filtering and product search

**File:** `tests/cartly/search-category-intersection.spec.ts`

**Steps:**
  1. Start from a clean browser context, enter a matching product search, then select Electronics.
    - expect: The listing represents the intersection of the selected category and search term, not unrelated matches.
    - expect: Category selection, query, count, and visible products remain mutually consistent.
  2. Clear the search while leaving Electronics selected, then select All categories.
    - expect: Clearing search retains the selected category if that is the documented interaction; switching to All categories restores the full catalog.
    - expect: No stale or contradictory filter state remains.

### 3. S3 — Product details and wishlist state

**Seed:** `tests/seed.spec.ts`

#### 3.1. TC-012 — Open and inspect a product detail dialog

**File:** `tests/cartly/product-details.spec.ts`

**Steps:**
  1. Start from a clean browser context, select Electronics, and activate View SoundWave Pro Wireless Headphones.
    - expect: A modal dialog opens with a product-specific accessible name and a Close product details control.
    - expect: The dialog shows the correct product name, brand, rating/count, current and former prices, description, product image alternative text, and wishlist action.
    - expect: The dialog explicitly communicates that this is a sample product and live purchasing is unavailable; no misleading checkout action is presented.

#### 3.2. TC-013 — Close product details through supported dismissal methods

**File:** `tests/cartly/product-dialog-close.spec.ts`

**Steps:**
  1. Start from a clean browser context, open a product detail dialog, and activate its Close product details button.
    - expect: The dialog closes and the prior listing state is restored.
  2. Open the dialog again and press Escape; if backdrop dismissal is specified, test that separately.
    - expect: Escape closes the dialog when supported and focus returns to the invoking product control.
    - expect: The dialog does not close unexpectedly when interacting with its own content.

#### 3.3. TC-014 — Add a product to wishlist from its detail dialog

**File:** `tests/cartly/wishlist-add-from-details.spec.ts`

**Steps:**
  1. Start with an empty wishlist in a clean browser context, open a product detail dialog, and activate Save to wishlist.
    - expect: The control changes to a saved state with an accessible name/state update.
    - expect: The header wishlist count increments to one and the saved state is reflected on the matching product card.
  2. Open Wishlist from the header.
    - expect: The wishlist heading and count show one item and the saved product appears with matching product details.
    - expect: The saved product exposes an Unsave action.

#### 3.4. TC-015 — Remove a wishlist item and verify the empty state

**File:** `tests/cartly/wishlist-remove-empty.spec.ts`

**Steps:**
  1. Start with a clean browser context, add a product to wishlist, and open Wishlist.
    - expect: The selected product is present and the count is one.
  2. Activate Unsave for the only saved product.
    - expect: The wishlist count becomes zero and the product is removed.
    - expect: The empty wishlist state is informative and provides a usable way to continue browsing if specified.

#### 3.5. TC-016 — Add and remove an item using the product-card control

**File:** `tests/cartly/wishlist-card-toggle.spec.ts`

**Steps:**
  1. Start with an empty wishlist, select a populated category, and activate Save on a product card.
    - expect: The card control changes to a pressed/saved state and the header count increments exactly once.
  2. Activate the same card control again.
    - expect: The product is removed, the count returns to zero, and the card control returns to its unsaved state.
    - expect: Repeated activation does not create duplicate wishlist entries or a stale count.

#### 3.6. TC-017 — Keep wishlist contents coherent while searching and filtering

**File:** `tests/cartly/wishlist-filtering.spec.ts`

**Steps:**
  1. Start with a clean browser context and add two products from different categories to the wishlist.
    - expect: The header count reflects two distinct saved products.
  2. Open Wishlist, apply a search query, and navigate between category views if supported in wishlist mode.
    - expect: Displayed results obey the active filter/search and contain only saved matching items.
    - expect: Changing or clearing filters does not remove saved items or corrupt the total wishlist count.

#### 3.7. TC-018 — Verify wishlist persistence against the approved persistence requirement

**File:** `tests/cartly/wishlist-reload-requirement.spec.ts`

**Steps:**
  1. Confirm with the product owner whether wishlist contents should persist after reload, across browser sessions, or only during the current page session; record the requirement before execution.
    - expect: The persistence expectation and test context are recorded; do not infer cross-session persistence from the current UI alone.
  2. Save one product, reload the page, then inspect the wishlist using the approved persistence expectation.
    - expect: Observed persistence matches the confirmed product requirement and the displayed count/content remain consistent.
    - expect: If no requirement exists, mark the case blocked by requirement clarification rather than pass or fail by assumption.

### 4. S4 — Accessibility, responsive behavior, compatibility, and resilience

**Seed:** `tests/seed.spec.ts`

#### 4.1. TC-019 — Operate primary shopping flows with keyboard only

**File:** `tests/cartly/keyboard-accessibility.spec.ts`

**Steps:**
  1. Start from a clean browser context and use only keyboard navigation from the document start through search, categories, product cards, wishlist, and product details.
    - expect: All interactive controls can be reached in a logical order and activated without a pointer.
    - expect: A visible focus indicator is present at every step and focus is not lost behind overlays.
  2. Open a product detail dialog, navigate its controls, and close it with keyboard.
    - expect: Dialog semantics and accessible name are announced; focus is managed within the modal as appropriate and returned to the opener after closing.
    - expect: Escape and standard keyboard activation work consistently where supported.

#### 4.2. TC-020 — Audit names, roles, states, images, contrast, and zoom

**File:** `tests/cartly/accessibility-audit.spec.ts`

**Steps:**
  1. Run an accessibility-tree review and an automated WCAG 2.2 AA scan on the landing page, category results, empty state, wishlist, and product dialog.
    - expect: Search, category selection, sort, carousel, wishlist, and dialog controls have understandable accessible names, roles, and current states.
    - expect: Meaningful product/offer images have appropriate text alternatives; decorative imagery is ignored by assistive technology.
    - expect: No serious/critical automated accessibility violations remain; manually verify contrast, headings, errors/empty state announcements, and zoom/reflow because automated tools do not cover all requirements.
  2. Test browser zoom at 200% and 400% on a desktop viewport.
    - expect: Content and controls remain readable and usable without loss of information or two-dimensional scrolling except where inherently required.

#### 4.3. TC-021 — Verify responsive layout at mobile, tablet, and desktop widths

**File:** `tests/cartly/responsive-layout.spec.ts`

**Steps:**
  1. Start from a clean browser context and inspect the root page at viewport widths 320, 375, 768, 1024, and 1440 CSS pixels.
    - expect: Navigation, search, featured offers, product grid, product dialog, wishlist, and footer adapt to the viewport without clipped controls or unintended horizontal overflow.
    - expect: Text remains readable, interactive targets remain usable, and layout changes do not hide essential actions.
  2. At mobile width, open/close product details and add/remove a wishlist item.
    - expect: Modal content and buttons fit the viewport or scroll within the dialog; core shopping preview interactions remain operable by touch-sized targets and keyboard.

#### 4.4. TC-022 — Check current stable browser compatibility

**File:** `tests/cartly/browser-compatibility.spec.ts`

**Steps:**
  1. Execute the critical landing, category, search, product dialog, and wishlist flows in current stable Chromium, Firefox, and WebKit/Safari where available.
    - expect: Core behavior and displayed catalog state are consistent across supported browsers.
    - expect: No browser-specific uncaught exceptions, unusable controls, layout breakage, or material visual regressions appear. Record exact browser and OS versions.

#### 4.5. TC-023 — Verify graceful behavior with slow or unavailable image resources

**File:** `tests/cartly/network-resilience.spec.ts`

**Steps:**
  1. Using browser network controls, throttle the connection and load the landing page and a product category.
    - expect: Core text, navigation, and controls remain usable while imagery loads slowly.
    - expect: Loading does not leave permanent blocking skeletons or cause the product grid to become unusable.
  2. Simulate image-resource failures without blocking the application document or scripts.
    - expect: Image failures produce a stable fallback or empty image area without broken layout or inaccessible controls.
    - expect: Failures are diagnosable in browser network evidence and do not falsely imply a completed purchase.

#### 4.6. TC-024 — Check runtime errors during representative user journeys

**File:** `tests/cartly/console-runtime.spec.ts`

**Steps:**
  1. Start from a clean context and exercise landing load, category filtering, matching/no-match search, product detail open/close, wishlist add/remove, and sort changes while monitoring console and failed requests.
    - expect: No uncaught JavaScript exception or application-owned failed request prevents a tested interaction.
    - expect: Any third-party/editor badge or expected blocked telemetry request is separated from application defects and recorded with context.
