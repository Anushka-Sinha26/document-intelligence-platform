\# Document Intelligence Platform — Architecture



\## 1. System Overview



The Document Intelligence Platform is an AI-powered system for extracting and validating information from financial documents.



The system supports four document types:



\- Invoice

\- Balance Sheet

\- Profit \& Loss

\- Cash Flow Statement



The user selects the document type, uploads the document, and the application processes it through validation, OCR/text extraction, AI-based structured extraction, financial validation, database persistence, and result presentation.



\---



\## 2. End-to-End Architecture



```mermaid

flowchart TD



&#x20;   A\[User] --> B\[Frontend Dashboard]



&#x20;   B --> C\[POST /api/v1/documents/process]



&#x20;   C --> D\[Document Validation Service]



&#x20;   D -->|Invalid / Unsupported| E\[FAILED Response]



&#x20;   D -->|Valid Document| F\[OCR / Text Extraction Service]



&#x20;   F --> G\[Page-Level Extracted Text]



&#x20;   G --> H\[Gemini Extraction Service]



&#x20;   H --> I\[Structured Extraction Result]



&#x20;   I --> J\[Financial Validation Service]



&#x20;   J --> K\[Processing Status]



&#x20;   I --> L\[Document Repository]

&#x20;   J --> L



&#x20;   L --> M\[(SQLite Database)]



&#x20;   K --> N\[REST API Response]



&#x20;   M --> O\[GET Document / List Documents]



&#x20;   N --> B

&#x20;   O --> B



&#x20;   B --> P\[Dashboard Results]



Perfect. ✅ README is now in place.



We are moving to the \*\*next submission requirement: Architecture Documentation\*\*.



We will keep this strictly aligned with the case study—no extra technologies or unnecessary components.



\### Step 1 — Create the architecture document



You are currently in:



```text

C:\\document-intelligence-platform\\backend>

```



Run:



```cmd

notepad ..\\docs\\architecture.md

```



If Notepad asks whether to create the file, click \*\*Yes\*\*.



\### Step 2 — Paste this entire content



````markdown

\# Document Intelligence Platform — Architecture



\## 1. System Overview



The Document Intelligence Platform is an AI-powered system for extracting and validating information from financial documents.



The system supports four document types:



\- Invoice

\- Balance Sheet

\- Profit \& Loss

\- Cash Flow Statement



The user selects the document type, uploads the document, and the application processes it through validation, OCR/text extraction, AI-based structured extraction, financial validation, database persistence, and result presentation.



\---



\## 2. End-to-End Architecture



```mermaid

flowchart TD



&#x20;   A\[User] --> B\[Frontend Dashboard]



&#x20;   B --> C\[POST /api/v1/documents/process]



&#x20;   C --> D\[Document Validation Service]



&#x20;   D -->|Invalid / Unsupported| E\[FAILED Response]



&#x20;   D -->|Valid Document| F\[OCR / Text Extraction Service]



&#x20;   F --> G\[Page-Level Extracted Text]



&#x20;   G --> H\[Gemini Extraction Service]



&#x20;   H --> I\[Structured Extraction Result]



&#x20;   I --> J\[Financial Validation Service]



&#x20;   J --> K\[Processing Status]



&#x20;   I --> L\[Document Repository]

&#x20;   J --> L



&#x20;   L --> M\[(SQLite Database)]



&#x20;   K --> N\[REST API Response]



&#x20;   M --> O\[GET Document / List Documents]



&#x20;   N --> B

&#x20;   O --> B



&#x20;   B --> P\[Dashboard Results]

````



\---



\## 3. Processing Flow



\### Step 1 — Document Upload



The user selects one of the supported document types:



```text

invoice

balance\_sheet

profit\_and\_loss

cash\_flow\_statement

```



The frontend sends the selected document and document type to:



```text

POST /api/v1/documents/process

```



The request uses `multipart/form-data`.



\---



\### Step 2 — Document Validation



The uploaded file is validated before OCR or AI extraction.



Validation checks include:



\* Supported file extension

\* File signature

\* File type consistency

\* Empty file detection

\* Corrupted file detection

\* PDF readability

\* PDF encryption

\* Page count

\* Image readability

\* Basic image integrity



Supported formats:



```text

PDF

JPG

JPEG

PNG

```



The maximum document size in terms of pages is 3 pages.



If validation fails, processing stops and the system returns a failed result.



\---



\### Step 3 — Native Text Extraction / OCR



The OCR service processes the validated document.



For PDF documents:



```text

PDF

&#x20;↓

Attempt native text extraction

&#x20;↓

Usable text?

&#x20;├── Yes → Use extracted text

&#x20;└── No  → Perform OCR

```



For image documents:



```text

JPG / JPEG / PNG

&#x20;↓

OCR

&#x20;↓

Extracted text

```



The system uses:



\* PyMuPDF

\* Tesseract OCR

\* pytesseract

\* Pillow



Page numbers are preserved during extraction.



\---



\### Step 4 — AI Structured Extraction



The extracted page-level text is passed to the Gemini extraction service.



Gemini is instructed to extract information explicitly present in the document.



The extraction includes:



\* Document metadata

\* Document number

\* Dates

\* Company/party information

\* Currency

\* Financial fields

\* Financial line items

\* Comparative-period values

\* Tables

\* Table rows

\* Page numbers

\* Evidence/source text where available



The model is instructed:



\* Do not invent values.

\* Do not infer missing information.

\* Return `null` for missing or unreadable values.

\* Use only the supplied document text.

\* Do not perform financial validation.



The AI response is constrained using a Pydantic structured schema.



\---



\## 4. Structured Extraction Layer



The extraction service returns a structured result containing:



```text

document\_metadata

fields

line\_items

tables

```



Each extracted field can contain:



```text

name

value

page\_number

evidence

```



Financial line items can contain:



```text

name

value

period

page\_number

evidence

```



Tables contain:



```text

title

columns

rows

page\_number

```



\---



\## 5. Financial Validation Layer



Financial validation is performed separately from AI extraction.



The application uses deterministic calculations with a tolerance of:



```text

0.01

```



\### Invoice



```text

Subtotal + Tax + Shipping/Handling ≈ Total

```



\### Balance Sheet



```text

Total Assets ≈ Total Capital and Liabilities

```



\### Profit \& Loss



```text

Interest Earned + Other Income ≈ Total Income

```



```text

Interest Expended

\+ Operating Expenses

\+ Provisions

≈ Total Expenditure

```



```text

Total Income - Total Expenditure

≈ Consolidated Net Profit Before Minority Interest

```



```text

Profit Before Minority Interest - Minority Interest

≈ Attributable Group Profit

```



\### Cash Flow Statement



```text

Operating + Investing + Financing + Foreign Exchange

≈ Net Increase in Cash

```



```text

Opening Cash + Net Increase in Cash

≈ Closing Cash

```



If a required value is unavailable, the corresponding validation check is:



```text

NOT\_APPLICABLE

```



The application does not modify extracted values to force a validation to pass.



\---



\## 6. Processing Status



The processing status is determined after document processing and validation.



Possible overall outcomes include:



```text

PASS

FAILED

```



A financial validation failure results in:



```text

FAILED

```



An unsupported, corrupted, invalid, or unprocessable document also results in:



```text

FAILED

```



\---



\## 7. Persistence Layer



Processing results are stored using:



```text

Flask-SQLAlchemy

&#x20;       ↓

SQLite

```



The database stores:



\* Document name

\* Document type

\* Processing status

\* File type

\* Page count

\* Extracted data

\* Validation result

\* Processing metadata

\* Created timestamp

\* Updated timestamp



The repository layer is responsible for database persistence and retrieval.



\---



\## 8. API Layer



The REST API is implemented using Flask and Flask-Smorest.



Required endpoints:



```text

POST /api/v1/documents/process

GET  /api/v1/documents/{document\_name}

GET  /api/v1/documents

GET  /api/v1/health

```



Swagger/OpenAPI documentation is exposed for API testing and inspection.



\---



\## 9. Frontend Layer



The frontend is implemented using:



\* HTML

\* CSS

\* JavaScript



The dashboard provides:



\* Document type selection

\* Document upload

\* Processing action

\* Processed document list

\* Processing status

\* Extracted information

\* Financial validation results

\* Raw JSON result

\* API connection status



The frontend communicates with the Flask backend API.



For deployment, the frontend must communicate with the deployed API rather than assuming a localhost backend.



\---



\## 10. Error Handling



Errors are handled at different stages of the pipeline.



\### File-level errors



Examples:



```text

Unsupported file type

Empty file

Corrupted file

File type mismatch

Too many pages

Unreadable document

```



\### Extraction errors



Examples:



```text

No extracted text

Empty AI response

Invalid structured AI response

Unsupported document type

```



\### Validation errors



Examples:



```text

Financial calculation mismatch

Missing required financial field

```



The application logs processing and repository errors and returns structured responses where applicable.



\---



\## 11. Separation of Responsibilities



The implementation separates major responsibilities into dedicated services.



```text

document\_validation\_service.py

&#x20;       ↓

Validates uploaded documents



ocr\_service.py

&#x20;       ↓

Extracts native text / performs OCR



extraction\_service.py

&#x20;       ↓

Uses Gemini for structured extraction



financial\_validation\_service.py

&#x20;       ↓

Performs deterministic financial checks



document\_service.py

&#x20;       ↓

Coordinates document processing



document\_repository.py

&#x20;       ↓

Persists and retrieves results

```



This separation avoids placing the complete processing pipeline inside a single large file.



\---



\## 12. Security



Basic security practices include:



\* API keys stored in environment variables

\* `.env` excluded from version control

\* Uploaded file validation before processing

\* Unsupported file rejection

\* Corrupted file rejection

\* Page-count restriction

\* Temporary file cleanup

\* No hardcoded AI API credentials



Secrets must not be committed to the public repository.



\---



\## 13. Observability



Application logging is configured using Python's logging facilities.



Logging is used for important processing and database events, including:



\* Document processing events

\* Repository operations

\* Exceptions

The system can therefore be debugged without placing all logic into the API route layer.



\---



\## 14. Design Principles



The architecture follows these principles:



\### Validate before processing



Documents are validated before OCR and AI extraction.



\### AI for extraction, deterministic logic for validation



Gemini is responsible for extracting information.



Financial correctness is checked by application logic rather than asking the AI model to perform accounting validation.



\### Source-grounded extraction



The extraction system uses only supplied document text.



\### No invented values



Missing or unreadable values are represented as `null`.



\### Persistence



Processing results are stored so they can be retrieved later through the API and displayed on the dashboard.



\### Separation of concerns



Validation, OCR, extraction, financial validation, persistence, API routing, and frontend presentation are kept separate.



\---



\## 15. Deployment Architecture



The final deployed architecture is:



```text

&#x20;                   Internet

&#x20;                      │

&#x20;                      ▼

&#x20;             ┌─────────────────┐

&#x20;             │ Frontend        │

&#x20;             │ Dashboard       │

&#x20;             └────────┬────────┘

&#x20;                      │

&#x20;                      │ HTTP API

&#x20;                      ▼

&#x20;             ┌─────────────────┐

&#x20;             │ Flask Backend   │

&#x20;             │ REST API        │

&#x20;             └────────┬────────┘

&#x20;                      │

&#x20;         ┌────────────┼────────────┐

&#x20;         │            │            │

&#x20;         ▼            ▼            ▼

&#x20;    Validation       OCR        Gemini API

&#x20;         │            │            │

&#x20;         └────────────┼────────────┘

&#x20;                      │

&#x20;                      ▼

&#x20;            Financial Validation

&#x20;                      │

&#x20;                      ▼

&#x20;             SQLite Persistence

&#x20;                      │

&#x20;                      ▼

&#x20;                API Response

&#x20;                      │

&#x20;                      ▼

&#x20;                 Dashboard

```



The deployment must expose:



```text

Public Frontend URL

Public Backend API URL

Public Swagger URL

Public Health Endpoint

Public GitHub Repository

```



\---



\## 16. Architecture Summary



The system follows the required end-to-end case-study architecture:



```text

Upload

&#x20; ↓

Validate

&#x20; ↓

Extract Text / OCR

&#x20; ↓

Gemini Structured Extraction

&#x20; ↓

Financial Validation

&#x20; ↓

Determine PASS / FAILED

&#x20; ↓

Persist Result

&#x20; ↓

REST API

&#x20; ↓

Frontend Dashboard

```





