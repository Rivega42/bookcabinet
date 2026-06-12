# RFID Library Self-Service Kiosk - Design Guidelines

## Design Approach

**Selected Framework**: Material Design 3 (adapted for kiosk environment)
**Justification**: Touch-optimized components, robust state system, clear hierarchy perfect for self-service terminals

## Typography System

**Font Family**: Roboto (via Google Fonts CDN)

**Hierarchy**:
- Display/Headlines: 48px bold (screen titles, welcome messages)
- Section Headers: 32px medium (operation stages, card titles)
- Body Text: 24px regular (instructions, descriptions)
- Button Labels: 28px medium (all interactive elements)
- Status Text: 20px regular (system messages, counters)
- Metadata: 18px regular (timestamps, secondary info)

All text uses high contrast ratios (4.5:1 minimum) for accessibility.

## Layout System

**Spacing Units**: Tailwind 4, 6, 8, 12, 16 (p-4, mb-6, gap-8, py-12, px-16)

**Grid Structure**:
- Full-screen layouts (no scrolling for primary flows)
- 3-column action grids for role selection (grid-cols-3 gap-8)
- 2-column layouts for operation details (form + status display)
- Single-column centered flows for step-by-step processes

**Touch Targets**: Minimum 64px height for all interactive elements, 80px preferred for primary actions

## Component Library

### Navigation & Structure

**Role Selection Screen** (Home):
- Three large card buttons (each ~400x300px) in centered grid
- Each card: icon (96px), role title, brief description
- Simple header with library logo/name (h-20)
- Footer with system status bar (h-16)

**Operation Header**:
- Fixed top bar (h-24) with: back button (left), operation title (center), system status indicators (right)
- Breadcrumb trail for multi-step operations

### Interactive Elements

**Primary Buttons**:
- Height: 80px, full-rounded corners (rounded-2xl)
- Large text (28px) with generous padding (px-12 py-6)
- Icons alongside text (32px size)

**Secondary Buttons**:
- Height: 64px, semi-rounded (rounded-xl)
- Consistent padding, slightly smaller icons (24px)

**Action Cards** (for book operations):
- Elevated containers with 24px padding
- Book thumbnail + metadata + action button
- Clear separation between items (gap-6)

### Status & Feedback

**Progress Indicators**:
- Linear progress bars (h-3, rounded-full)
- Circular spinners for scanning operations (96px diameter)
- Step indicators for multi-stage flows (numbered circles connected by lines)

**Status Badges**:
- Pill-shaped (rounded-full), 40px height
- Icon + text combination
- Success (green), Error (red), Warning (yellow), Info (blue)

**System Status Panel** (footer):
- RFID reader status
- Network connection
- Available slots count
- Last operation timestamp

### Forms & Inputs

**User Identification**:
- Large card/barcode scanner target area (400x250px)
- Visual feedback during scan (pulsing animation)
- Clear "Scan your library card" instruction

**Numeric Keypad** (if needed):
- 4x3 grid, 96x96px buttons
- Large numbers (36px)

**Book List Display**:
- Scrollable container (when needed) with large touch-friendly cards
- Each book: thumbnail (120x160px), title (24px bold), author (20px), status badge

### Librarian & Admin Interfaces

**Inventory Management**:
- 2-column layout: slot grid visualization (left), operation panel (right)
- Slot grid shows cabinet layout with status colors
- Drag-drop zones for book loading (minimum 200x200px)

**Admin Dashboard**:
- 4-card metrics grid (2x2): transactions today, system health, errors, storage utilization
- Tabbed interface for: diagnostics, settings, logs, reports
- Data tables with 56px row height for touch selection

## Animation Guidelines

**Minimal Use**:
- State transitions: 200ms ease-out
- Progress updates: smooth fills (300ms)
- Scanning feedback: subtle pulse (1s cycle)
- NO decorative animations, NO hover effects (touch interface)

## Images

No hero images required. All graphics are functional:
- Library logo/branding in header (SVG, max 200x60px)
- Book cover thumbnails (fetched from catalog, 120x160px ratio)
- Iconography from Material Symbols (via CDN)
- System diagrams for admin diagnostics (schematic style)

## Accessibility Considerations

- High contrast throughout (no subtle grays)
- Touch targets never overlap or crowd
- Clear focus indicators for keyboard navigation (admin mode)
- Text never over complex backgrounds
- Status communicated through multiple channels (color + icon + text)
- Language toggle prominent (multi-language library support)

## Screen Flows

**Reader Flow**: Role select → Card scan → Choose action (borrow/return) → Book scan → Confirmation → Receipt
**Librarian Flow**: Role select → Login → Choose operation (load/unload) → Slot selection → Book processing → Summary
**Admin Flow**: Role select → Secure login → Dashboard → Tool selection → Operations → Logout

All flows use consistent 3-step maximum before completion, with clear "Cancel" and "Back" options at each stage.