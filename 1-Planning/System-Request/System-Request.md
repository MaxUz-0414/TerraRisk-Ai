# System Request: TerraRisk AI

| | |
|---|---|
| **Project name** | TerraRisk AI |
| **Owner of this document** | Abduraimboy Murodullaev (Project Leader, ID 2401248) |
| **Reviewers** | all team members (see the RACI matrix, row P-01) |
| **Version / date** | 1.0, 19 November 2026 |
| **Project sponsor** | *[to fill in: instructor / client name and title]* |
| **Prepared by** | the TerraRisk team (six students) |

> Everything below that describes the product is taken from the repository (`4-Implementation/README.md`,
> `ARCHITECTURE.md`, the code and the RTM). Lines in *[italics and brackets]* are facts only the team or the sponsor can
> supply; fill them in before the document is submitted.

## 1. Business need

Flood and landslide risk on a piece of land is decided by what happens *upstream*: steep slopes, nearby rivers, vegetation
loss, heat, and ground that is already saturated. None of that is visible on an ordinary map. People who must decide where
to plant, which property to buy or which asset to finance have no quick, plain-language way to see it.

TerraRisk AI answers one question for three kinds of user ("personas"):

| Persona | Question the results page answers |
|---|---|
| Farmer | Is this field safe to plant, and what should I do about water and heat? |
| Home buyer | Is this property in a risky place, and what should I ask before buying? |
| Investor | What are the due-diligence flags, and how does the risk change in a hotter or drier future? |

## 2. Business requirements

The system must (full list with IDs in [`2-Analysis/Requirements/Requirements-and-Use-Cases.md`](../../2-Analysis/Requirements/Requirements-and-Use-Cases.md)):

1. let a visitor register, sign in and choose a persona (FR-01);
2. let a user find a place by name and draw a parcel (polygon or pin) with a 3 to 5 km hazard buffer on a satellite map (FR-02, FR-03);
3. compute satellite features and a risk score from a flood model and a landslide model (FR-04, FR-05, ML-01 to ML-03);
4. show a results page tailored to the persona, with written advice and four satellite pictures (FR-05, FR-06);
5. produce a multi-page PDF certificate (FR-07);
6. sell analyses through plans (free signup searches, five paid plans) and never lose or double-charge a credit (FR-08, FR-14, NFR-08);
7. offer a help chatbot, a support page and an administrator dashboard (FR-09, FR-10, FR-16);
8. keep working, as far as possible, when one service is down (NFR-01).

## 3. Business value

**Tangible**

| Item | Basis |
|---|---|
| Revenue per analysis | Plans in `services/billing/tr_billing/plans.py`: Starter $4.99 (20 analyses, about $0.25 each), Plus $6.99 (30, $0.23), Pro $9.99 (50, $0.20), Business $17.99 (100, $0.18), Unlimited $29.00 (30 days) |
| Free trial | Every new account starts with 5 free searches |
| Expected number of paying users | *[to fill in: the team's estimate and where it comes from]* |

Checkout is a demo today (nobody is charged); a real payment provider is a planned requirement (FR-18).

**Intangible**: a working example of splitting a monolith into services (the cloud-computing course method), a portfolio
project that runs live, and an honest, documented example of using satellite data and machine learning for a social good.

## 4. Special issues and constraints

- **Data licences.** Real satellite data comes from Google Earth Engine, which is registered for non-commercial use;
  commercial use needs a licence. Esri and Google map imagery have their own terms.
- **Third-party policies.** The place-name service (Nominatim) allows one request per second and requires an identifying
  User-Agent; the geocode service enforces this and caches answers.
- **Scores are screening indices**, not engineering, insurance or legal opinions. The flood model is trained on labels made
  from a formula plus noise; the landslide model has a cross-validated AUC of about 0.70.
- **Payments are a demo.** No card data is ever handled by our code.
- **Team constraint.** Six students, one semester, one shared repository with a Leader-reviewed pull-request workflow.
- **Deadline / milestones.** *[to fill in]*
