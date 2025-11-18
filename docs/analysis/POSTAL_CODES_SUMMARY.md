# Postal Codes Added to 100 Leads

**Date:** November 17, 2025
**Source:** OpenStreetMap Nominatim (FREE Geocoding Service)
**Result:** 76/100 postal codes successfully added (76% success rate)

---

## Files

### Input
- `100_LEADS_STANDARDIZED_FORMAT.csv` - Original with "Unknown" postal codes

### Output
- **`100_LEADS_WITH_POSTAL_CODES.csv`** - ✅ Updated with real postal codes

---

## Results

| Metric | Count | Percentage |
|--------|-------|------------|
| **Postal codes added** | 76 | 76% |
| **Not found** | 24 | 24% |
| **Total leads** | 100 | 100% |

---

## Leads Missing Postal Codes (24)

The following leads still show "Unknown" for postal codes (incomplete addresses or not in OSM database):

### Manufacturing (2)
- AVL Hamilton
- Innovation Factory

### Wholesale (1)
- Mercury Foodservice Ltd

### Professional Services (13)
- Wentworth Strategy Group
- Stubii
- Satori Consulting Inc
- Mc Cann Corporate Consulting
- Pro Act Consulting Inc
- Dillon Consulting Limited
- Hamilton Business Consulting
- NBG Chartered Professional Accountant
- Binatech System Solutions
- Southbrook Consulting.

### Printing (4)
- Hamilton Printing
- Copy Point
- Minuteman Press
- Next day t-shirts

### Equipment Rental (4)
- Battlefield Equipment Rentals
- Stoney Creek Equipment Rentals
- All Star Equipment Rental
- Cooper Equipment Rentals
- Edge1 Equipment Rentals
- Skylift Rentals Ltd
- United Rentals

---

## Postal Code Examples

Here are some of the successfully added postal codes:

| Business Name | Address | Postal Code |
|---------------|---------|-------------|
| Mondelez Canada | 45 Ewen Rd | **L8S 3C4** |
| The Cotton Factory | 270 Sherman Ave N | **L8L 3A9** |
| Karma Candy Inc | 356 Emerald St N | **L8L 2X5** |
| Orlick Industries Ltd. | 411 Parkdale Ave N | **L8H 5X9** |
| The Spice Factory | 121 Hughson St. N | **L8R 1G7** |
| National Steel Car | 600 Kenilworth Ave N | **L8H 2V4** |
| Ontario Ravioli | 121 Brockley Dr | **L8E 3C2** |
| sweet & simple co. | 942 Main St E | **L8M 2Y7** |

---

## Hamilton Postal Code Coverage

The leads cover these Hamilton postal code areas:

- **L8S** - West Hamilton (Ainslie Wood, Westdale)
- **L8L** - North End, Sherman Ave
- **L8H** - North End, Kenilworth
- **L8E** - East Hamilton, Stoney Creek
- **L8M** - Central East
- **L8R** - Downtown core
- **L8P** - West Mountain
- **L8K** - Central Mountain
- **L8W** - Waterdown area
- **L9C** - Ancaster
- **L9A** - Dundas

---

## What To Do With Missing Postal Codes

For the 24 leads with "Unknown" postal codes, you can:

1. **Manual Lookup:** Google the business name + address to find postal code
2. **Contact Verification:** Call the business and ask for their full mailing address
3. **Use Them As-Is:** You still have street address, city, and province
4. **Skip Them:** Focus on the 76 leads with complete addresses

---

## Technical Details

### Geocoding Method
- **Service:** OpenStreetMap Nominatim API
- **Cost:** FREE (no API key required)
- **Rate Limit:** 1 request per second (per OSM usage policy)
- **Total Time:** ~100 seconds (~2 minutes)

### Why Some Failed
Postal codes couldn't be found for these reasons:
- Incomplete street addresses (e.g., "at the end of")
- New buildings not yet in OpenStreetMap
- Business name used instead of street address
- Consulting firms with virtual/shared offices

---

## Next Steps

✅ **Your leads are ready!**
Use the file: **`data/outputs/100_LEADS_WITH_POSTAL_CODES.csv`**

This file includes:
- Business Name, Full Address with Postal Code
- Phone Number, Website
- Estimated Employees (Range)
- Estimated SDE (CAD)
- Estimated Revenue (CAD)
- Confidence Score, Status

---

**Generated:** November 17, 2025
**Service:** OpenStreetMap Nominatim
**Success Rate:** 76%
**Ready for Use:** ✅
