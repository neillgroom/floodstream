# VenueOTR PDF Reverse-Engineering Reference

> Extracted 2026-03-22 from the Venue Claims iOS app (SCH.imazingapp)
> via iMazing backup. This documents exactly how Venue generates their
> Adjuster's Preliminary Report PDF so FloodStream can replicate the
> layout with better quality.

## Source App Details

- **App:** com.venueclaims.venuemobile (Xamarin.Forms / C#/.NET)
- **PDF Library:** iText 7.1.6 (.NET / AGPL version)
- **Database:** VenueSQLite.db3 (180MB SQLite, all claim data)
- **Structure:** iOS app backup → Container/Library/VenueSQLite.db3 + Container/Documents/VenuePhotos/

## PDF Structure (12 pages for a typical Prelim)

### Pages 1-2: FEMA Adjuster's Preliminary Report Form

Standard FEMA form (FF-206-FY-21-146). Our `fema_form.py` already handles this.

**Page 1 layout (top to bottom):**
```
┌─────────────────────────────────────────────────────────────┐
│ Date: 3/13/2026          DEPARTMENT OF HOMELAND SECURITY    │
│                    Federal Emergency Management Agency       │
│                   National Flood Insurance Program           │
│              ADJUSTER'S PRELIMINARY REPORT                  │
│              with (select all that apply)                    │
│ [x] Initial Reserves [ ] Advance Payment Request ...        │
├─────────────────────────────────────────────────────────────┤
│ Policyholder information                                    │
│  Policyholder: JYL CAPITAL...  │ Insurer: NFIP Direct       │
│  Property Address: 811...      │ Policy #: 5000025672       │
│  City: Chester  State: PA      │ Adjuster: Julio Lopez      │
│  Phone: 2679050589             │ Adjusting Firm: FG...       │
│  Email: ...                    │ File #: FG152134           │
├─────────────────────────────────────────────────────────────┤
│ Representative information (usually blank)                  │
├─────────────────────────────────────────────────────────────┤
│ Insurance information                                       │
│  Flood program: Regular  │ Cov A - Building: $225,000      │
│  SFIP policy: Dwelling   │ Deductible: $2,000              │
│  Term: 11/17/2025-2026   │ Reserve: $5,000  Advance: $0    │
│                          │ Cov B - Contents: $0             │
├─────────────────────────────────────────────────────────────┤
│ Property risk information                                   │
│  Occupancy: Single-family │ Flood zone: AE                  │
│  Building type: Main Dwelling │ Building over water: No     │
│  Occupied by: Tenant-occupied │ Under construction: No      │
└─────────────────────────────────────────────────────────────┘
```

**Page 2 layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ (Same FEMA header repeated)                                 │
├─────────────────────────────────────────────────────────────┤
│ Flood water information: Main building/unit                 │
│  Approx. date water entered: 02/23/2026  Time: 12:00PM     │
│  Approx. date water receded: 02/24/2026  Time: 12:00PM     │
│  Duration: 1 Days, 0 Hours, 0 Minutes                      │
│  Exterior water height: 1.00 = 0 feet 1 inches             │
│  Interior water height: -80.00 = -6 feet -8 inches         │
├─────────────────────────────────────────────────────────────┤
│ Adjuster's signature: [signature image]                     │
│                        Adjuster  FCN: 0005070169            │
│                        Date signed: 3/13/2026               │
└─────────────────────────────────────────────────────────────┘
```

### Pages 3+: Photo Sheet (THIS IS WHAT NEEDS THE LOGO)

**This is the critical layout to match.** Each photo page has:

#### Photo Sheet Header (bordered box at top of every photo page)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ┌──────────┐                                                           │
│  │          │  Insured:      JYL CAPITAL INVESTORS LLC                   │
│  │   [FG    │  LOCATION:    811 ELSINORE PL,         DATE OF REPORT:  3/13/2026│
│  │   LOGO]  │               Chester,PA,19013         DATE OF LOSS:    2/23/2026│
│  │          │                                        POLICY NUMBER:   5000025672│
│  │ FOUNTAIN │  COMPANY:     NFIP Direct              CLAIM NUMBER:    N999920260107│
│  │  GROUP   │               6330 SPRING PARKWAY,     OUR FILE NUMBER: FG152134│
│  │ ADJUSTERS│               SUITE 450                ADJUSTER NAME:   Julio Lopez│
│  │          │               OVERLAND PARK,KS,66211                     │
│  └──────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key details:**
- FG Logo is approximately 1" x 0.8", positioned in the LEFT of the header box
- Logo file: `fg_logo.jpg` (needs to be added to `pipeline/assets/`)
- The header is a bordered table/box, NOT free-floating text
- Left column: Logo
- Middle column: Insured, Location (address+city+state+zip), Company (carrier name) + carrier mailing address
- Right column: Date of Report, Date of Loss, Policy Number, Claim Number, Our File Number, Adjuster Name
- Carrier address (e.g. "6330 SPRING PARKWAY, SUITE 450, OVERLAND PARK, KS, 66211") comes from the NOL
- Font appears to be a monospace or condensed serif (Courier-like) for the data fields

#### Photo Layout (1 photo per page in Venue, below header)

```
Photo ID: Front of Risk
┌─────────────────────────────────┐    Photo ID: 1
│                                 │    Date: 03/12/2026
│                                 │    Taken By: Adjuster
│         [PHOTO IMAGE]           │    Comment: Risk is a single family,
│         ~4.5" x 3.5"           │    tenant occupied, pre firm, non
│                                 │    elevated over a basement and
│                                 │    located in risk zone AE.
│                                 │    Ext wm 1". Int wm -80" in the
│                                 │    basement. Duration 24 hours.
│                                 │    Advance payment discussed,
│                                 │    however insured will advise later.
└─────────────────────────────────┘
```

**Key details:**
- "Photo ID: [label]" appears ABOVE the photo as a title line
- Photo is on the LEFT, roughly 55% of page width
- Info panel on the RIGHT with: Photo ID number, Date, Taken By, Comment
- Comment text word-wraps in a narrow column
- Venue puts 1 photo per page (wasteful — FloodStream does 2 per page)

## What FloodStream Needs to Change

### 1. Add FG Logo to `pipeline/assets/`
- Save the FG Logo as `pipeline/assets/fg_logo.jpg`
- The logo is the 3D "FG" letters with green swoosh + "FOUNTAIN GROUP ADJUSTERS" text below

### 2. Update `photo_sheet.py` header to match Venue layout
Current header is basic text. Needs to become a bordered box with:
- Logo (left)
- Claim info (middle): Insured, Location, Company + carrier address
- Report info (right): Date of Report, Date of Loss, Policy #, Claim #, File #, Adjuster

### 3. Add carrier address to ClaimInfo dataclass
The photo sheet header includes the carrier's mailing address (from the NOL).
Add field: `company_address: str = ""` to `ClaimInfo`

### 4. Photo compression
Venue's photos are full-resolution (500KB+ each, 21MB total PDF for 12 pages).
FloodStream should:
- Resize photos to max 1200px on longest side
- JPEG compress at quality 60-70
- Target: ~100KB per photo, ~2-3MB total PDF

### 5. Photo label line
Add "Photo ID: [label]" as a title line ABOVE each photo (Venue does this, our current version doesn't).

## VenueOTR SQLite Database

The 180MB database (`VenueSQLite.db3`) contains all claim data that feeds
into the PDF. The Venue app reads from this DB and uses iText 7 to
generate the PDF on-device. FloodStream replaces this entire pipeline
with server-side Python (ReportLab) driven by Claude AI extraction.

## Files from VenueOTR Backup

```
SCH.imazingapp (219MB ZIP)
├── iTunesMetadata.plist
├── Payload/BlankAppShared.iOS.app/Info.plist  (compiled Xamarin app)
├── Container/
│   ├── Documents/
│   │   ├── VenuePhotos/
│   │   │   ├── FG142839/  (photos for claim FG142839)
│   │   │   ├── FG146118/
│   │   │   ├── FG151954/
│   │   │   └── FG152134/  (the claim in Prelim.pdf)
│   │   └── VenueAdjusterPhotos/647/  (Julio Lopez photos/signature)
│   └── Library/
│       └── VenueSQLite.db3  (180MB — all claims data)
```
