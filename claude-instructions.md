# Claude AI Task Instructions

## Overview
This document contains all prompts and instructions for Claude to execute the business acquisition MVP. Each phase has specific prompts that should be copied and used at the appropriate trigger points.

## Phase 1: Business Discovery Prompts

### Initial Search Prompt
```
Search for businesses in Hamilton, Ontario, Canada with these criteria:

MUST HAVE:
- Business appears to have revenue between $1-2M CAD
- Established 15+ years (look for "Since" or "Established" dates)
- Single location only
- Google rating 4.2 or higher
- Shows signs of 5-15 employees

SEARCH THESE SECTORS:
- Manufacturing companies Hamilton ON
- Wholesale distributors Hamilton ON
- Print shops Hamilton ON
- Equipment rental Hamilton ON
- Auto parts stores Hamilton ON
- Food distributors Hamilton ON
- Janitorial supplies Hamilton ON
- Office supplies Hamilton ON
- Packaging companies Hamilton ON
- Business services Hamilton ON
- Sign companies Hamilton ON
- Uniform suppliers Hamilton ON
- Industrial supplies Hamilton ON

EXCLUDE:
- Franchises
- Skilled trades (electricians, plumbers, HVAC)
- Professional services requiring licenses
- Multiple locations

For each business found, provide:
1. Business name
2. Address
3. Phone
4. Website
5. Google rating & review count
6. Years in business indicator
7. Estimated revenue range
8. Owner name (if found)
9. Email (if visible)
10. Acquisition score (1-100)
```

### Scoring Matrix Prompt
```
Score this business for acquisition potential (100 points total):

Business: [NAME]
Website: [URL]
Google Reviews: [RATING/COUNT]

Scoring Criteria:
- Revenue $1-2MM CAD: 20 points
- 15+ years in business: 15 points  
- Owner likely 50+ years old: 15 points
- Single location: 10 points
- Google rating 4.2-4.7: 10 points
- Static/outdated website: 10 points
- Team of 5-15 employees: 10 points
- Estimated SDE >$200k: 10 points

Provide:
1. Total score /100
2. Strengths for acquisition
3. Potential concerns
4. Recommended approach angle
```

## Phase 2: Deep Research Prompts

### Business Intelligence Prompt
```
Conduct deep research on [BUSINESS NAME] for acquisition:

Using "Buy then Build" methodology, analyze:

1. FINANCIAL ESTIMATES
- Revenue estimate based on:
  * Industry benchmarks
  * Employee count
  * Google traffic estimate
  * Review volume
- Likely SDE (Seller's Discretionary Earnings)
- Working capital requirements

2. OWNER PROFILE
- Approximate age (look for LinkedIn, news mentions)
- Years as owner
- Succession planning indicators
- Personal attachment to business

3. DIGITAL OPPORTUNITIES
- Website last updated
- SEO opportunities missed
- Social media presence gaps
- Online marketing potential
- E-commerce possibilities

4. COMPETITIVE LANDSCAPE
- Main competitors in Hamilton
- Market position
- Unique selling proposition
- Defensible advantages

5. ACQUISITION ATTRACTIVENESS
- "Buy then Build" opportunities
- Risk factors
- Integration complexity
- Growth potential post-acquisition

6. SUGGESTED APPROACH
- Best angle (legacy/growth/partnership)
- Key value propositions
- Likely objections
- Negotiation leverage points
```

### Review Analysis Prompt
```
Analyze the Google reviews for [BUSINESS NAME]:

From the recent reviews, identify:
1. Core strengths repeatedly mentioned
2. Any recurring complaints
3. Customer demographics
4. Loyalty indicators
5. Service/product gaps
6. Staff mentions (indicates team stability)
7. Owner involvement level
8. Pricing sensitivity indicators

Summarize acquisition implications from review sentiment.
```

## Phase 3: Email Creation Prompts

### Email Template Generation
```
Create 3 different email approaches for [BUSINESS NAME] acquisition outreach:

CONTEXT:
- Business: [NAME]
- Owner: [NAME]
- Years in business: [X]
- Key strength: [FROM RESEARCH]
- Opportunity: [FROM RESEARCH]
- Sending as: [BROKER NAME] from [BROKERAGE]

EMAIL 1: LEGACY PRESERVATION (under 150 words)
- Acknowledge specific achievement
- Respect for what they've built
- Interest in preserving legacy
- Soft mention of acquisition interest

EMAIL 2: GROWTH PARTNERSHIP (under 150 words)
- Note specific untapped opportunity
- Partnership/investment angle first
- Resources to help grow
- Acquisition as eventual option

EMAIL 3: DIRECT APPROACH (under 150 words)
- Straightforward acquisition interest
- Specific value proposition
- Confidential valuation offer
- Emphasis on preserving culture/team

Make each email:
- Highly personalized
- Reference specific details
- Non-threatening
- Professional but warm
```

### Follow-up Sequence Prompt
```
Create follow-up email sequence for [BUSINESS NAME]:

FOLLOW-UP 1 (Day 4 if no response):
- Reference original email briefly
- Add new value (industry insight or stat)
- Softer call to action

FOLLOW-UP 2 (Day 7 if no response):
- Different angle than original
- Mention specific opportunity you see
- Create urgency without pressure

FINAL FOLLOW-UP (Day 14):
- Acknowledge they may not be interested
- Leave door open for future
- Offer value regardless (market report, etc)

Each under 100 words.
```

## Phase 4: Email Finding Prompts

### Email Discovery Prompt
```
Generate email finding strategy for:
Business: [NAME]
Owner: [OWNER NAME]
Domain: [WEBSITE]

Provide:
1. Most likely email patterns:
   - firstname@domain
   - firstname.lastname@domain
   - firstinitial+lastname@domain
   - info@domain
   - owner@domain

2. Google search queries:
   - "[owner name]" "[business]" email
   - site:[domain] email
   - "[business name]" contact email

3. Hunter.io strategy:
   - Domain search
   - Name + domain combination

4. Website locations to check:
   - /contact
   - /about
   - Footer information
   - Team page

5. Verification method:
   - Email permutator results
   - Social media cross-reference
```

## Phase 5: Tracking System Prompts

### Google Sheets Structure
```
Create Google Sheets CRM structure:

SHEET 1: PROSPECTS
Columns:
- Business Name
- Owner Name
- Email
- Phone
- Website
- Revenue Estimate
- Years in Business
- Acquisition Score
- Initial Email Sent (Date)
- Follow-up 1 (Date)
- Follow-up 2 (Date)
- Response Status (No Reply/Cold/Warm/Hot)
- Response Date
- Meeting Scheduled
- Notes
- Next Action

SHEET 2: EMAIL TEMPLATES
- Business Name
- Email Version Used (1/2/3)
- Subject Line
- Open Tracking
- Response Rate

SHEET 3: ANALYTICS
- Total Sent
- Open Rate
- Response Rate
- Meeting Conversion
- Best Performing Template
- Average Response Time

Include formulas for:
- Automatic status updates
- Response rate calculations
- Follow-up reminders
- Performance metrics
```

## Phase 6: Response Management Prompts

### Response Handler Prompt
```
They replied to our acquisition inquiry:
Their response: "[PASTE RESPONSE]"

Business: [NAME]
Our original approach: [LEGACY/GROWTH/DIRECT]

Create appropriate response based on their tone:

If INTERESTED:
- Thank them for response
- Suggest specific meeting times
- Include Calendly link
- Build excitement about possibilities

If NEEDS MORE INFO:
- Address specific concerns
- Provide relevant information
- Maintain confidentiality where appropriate
- Soft push toward meeting

If NOT NOW:
- Respect their position
- Ask about better timing
- Offer to stay in touch
- Provide value (market report)

If OBJECTION:
- Acknowledge concern
- Provide reassurance
- Share relevant success story
- Redirect to benefits

Keep response under 150 words.
```

## Phase 7: Meeting Prep Prompts

### Meeting Brief Generation
```
Create meeting brief for broker:

BUSINESS: [NAME]
OWNER: [NAME]
MEETING DATE: [DATE]

Generate:

1. QUICK REFERENCE
- Key facts about business
- Owner hot buttons
- Estimated valuation range
- Our value proposition

2. STRATEGIC QUESTIONS (5-7)
- Discovery questions about operations
- Financial performance questions
- Owner motivation questions
- Growth challenge questions
- Exit timeline questions

3. LIKELY OBJECTIONS & RESPONSES
- "Not ready to sell"
- "Want more money"
- "Worried about employees"
- "Need to think about it"
- "Why should I trust you?"

4. DEAL STRUCTURE OPTIONS
- All cash offer
- Earnout possibilities
- Seller financing options
- Transition period arrangements

5. NEXT STEPS CHECKLIST
- Letter of Intent timeline
- Due diligence preview
- Key terms to negotiate
- Follow-up plan
```

## Phase 8: Analysis Prompts

### Performance Analysis Prompt
```
Analyze campaign performance:

METRICS:
- Emails sent: [X]
- Opens: [X]
- Responses: [X]
- Meetings booked: [X]

Provide:

1. PERFORMANCE ANALYSIS
- Open rate vs. industry benchmark (40%)
- Response rate vs. target (20%)
- Meeting conversion vs. goal (20% of responses)

2. TEMPLATE EFFECTIVENESS
- Best performing subject lines
- Most effective approach angle
- Optimal follow-up timing

3. INSIGHTS
- Common objections pattern
- Best responding business types
- Owner profile patterns

4. RECOMMENDATIONS
- Template improvements
- Targeting adjustments
- Process optimizations

5. SCALING PLAN
- If successful (2+ meetings): Scale to 100 businesses
- If moderate (1 meeting): Refine approach
- If unsuccessful (0 meetings): Pivot strategy
```

## Usage Instructions

1. Copy the relevant prompt for each phase
2. Fill in the [BRACKETED] information
3. Paste into Claude
4. Review output before proceeding
5. Save all outputs to Google Sheets

## Notes
- Always wait for trigger confirmation before proceeding
- Save all Claude outputs immediately
- Track prompt effectiveness for optimization