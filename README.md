\# Document Intelligence Platform



An AI-powered document extraction and validation platform for financial documents.



The system accepts invoices and financial statements, validates the uploaded file, extracts text using native PDF text extraction or OCR, uses Google Gemini for structured information extraction, performs financial consistency checks, stores the processing result in a database, and exposes the result through a REST API and web dashboard.



\---



\## 1. Project Objective



The objective of this project is to build an end-to-end document intelligence platform capable of processing financial documents and returning structured, validated information.



The supported document categories are:



\- Invoice

\- Balance Sheet

\- Profit \& Loss

\- Cash Flow Statement



The processing pipeline is:



```text

Document Upload

&#x20;     ↓

Document Validation

&#x20;     ↓

Native Text Extraction / OCR

&#x20;     ↓

AI Field \& Table Extraction

&#x20;     ↓

Structured JSON

&#x20;     ↓

Financial Calculation Validation

&#x20;     ↓

Confidence / Evidence

&#x20;     ↓

Database Persistence

&#x20;     ↓

PASS / FAILED

&#x20;     ↓

Dashboard + REST API



Great. Now replace \*\*everything\*\* in the open `README.md` with the following final version.



\# `README.md`



````markdown

\# Document Intelligence Platform



An AI-powered document extraction and validation platform for financial documents.



The system accepts invoices and financial statements, validates the uploaded file, extracts text using native PDF text extraction or OCR, uses Google Gemini for structured information extraction, performs financial consistency checks, stores the processing result in a database, and exposes the result through a REST API and web dashboard.



\---



\## 1. Project Objective



The objective of this project is to build an end-to-end document intelligence platform capable of processing financial documents and returning structured, validated information.



The supported document categories are:



\- Invoice

\- Balance Sheet

\- Profit \& Loss

\- Cash Flow Statement



The processing pipeline is:



```text

Document Upload

&#x20;     ↓

Document Validation

&#x20;     ↓

Native Text Extraction / OCR

&#x20;     ↓

AI Field \& Table Extraction

&#x20;     ↓

Structured JSON

&#x20;     ↓

Financial Calculation Validation

&#x20;     ↓

Confidence / Evidence

&#x20;     ↓

Database Persistence

&#x20;     ↓

PASS / FAILED

&#x20;     ↓

Dashboard + REST API

````



\---



\## 2. Key Features



\### Document validation



The application validates documents before OCR or AI extraction.



Supported formats:



\* PDF

\* JPG

\* JPEG

\* PNG



Validation includes:



\* File extension validation

\* File signature validation

\* File type mismatch detection

\* Empty file detection

\* Corrupted file detection

\* PDF readability validation

\* PDF encryption detection

\* Page count validation

\* Image readability validation

\* Basic image integrity checks



The maximum supported document length is 3 pages.



\---



\### OCR and text extraction



The system supports both native and scanned documents.



For PDFs:



1\. Native PDF text is attempted first.

2\. If usable text is not available, OCR is performed.



For image documents:



\* OCR is performed directly.



The OCR layer uses:



\* PyMuPDF

\* Tesseract OCR

\* Pillow

\* pytesseract



Page boundaries are preserved so extracted information can be associated with the source page.



\---



\### AI-powered extraction



Google Gemini is used for structured extraction.



The extraction service produces structured information containing:



\* Document metadata

\* General fields

\* Financial line items

\* Tables

\* Page numbers

\* Evidence/source text where available



The extraction prompt instructs the model to:



\* Extract all meaningful visible information

\* Use only information present in the source

\* Never invent or infer values

\* Return `null` when information is missing or unreadable

\* Preserve numeric values as strings

\* Extract comparative periods

\* Extract tables and table rows

\* Preserve page numbers

\* Provide source evidence where possible

\* Avoid performing financial calculations



Financial validation is performed separately by the application.



\---



\## 3. Supported Document Types



The frontend allows the user to select the document type before processing.



Supported values:



```text

invoice

balance\_sheet

profit\_and\_loss

cash\_flow\_statement

```



Automatic document classification is not required for this implementation.



\---



\## 4. Financial Validation



After extraction, the application performs deterministic financial consistency checks.



A tolerance of:



```text

0.01

```



is used for numerical comparisons.



\### Invoice



The system validates:



```text

Subtotal + Tax + Shipping/Handling ≈ Total

```



If required values are unavailable, the corresponding validation is returned as:



```text

NOT\_APPLICABLE

```



\---



\### Balance Sheet



The system validates:



```text

Total Assets ≈ Total Capital and Liabilities

```



\---



\### Profit \& Loss



The system validates:



```text

Interest Earned + Other Income ≈ Total Income

```



```text

Interest Expended + Operating Expenses + Provisions

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



\---



\### Cash Flow Statement



The system validates:



```text

Operating Cash Flow

\+ Investing Cash Flow

\+ Financing Cash Flow

\+ Foreign Exchange Effect

≈ Net Increase in Cash

```



and:



```text

Opening Cash + Net Increase in Cash

≈ Closing Cash

```



\---



### Validation result

Each validation check contains:

```json
{
  "formula": "...",
  "input_values": {},
  "calculated_value": "...",
  "reported_value": "...",
  "variance": "...",
  "status": "PASS"
}
```

Possible validation statuses are:

```text
PASS
FAIL
NOT_APPLICABLE
```



The application does not modify extracted financial values to force a validation to pass.



\---



\## 5. Processing Status



The final processing status indicates whether the document could be successfully processed and validated.



Examples:



```text

PASS

FAILED

```



A document can be successfully extracted but receive a `FAILED` processing status when a required financial consistency check fails.



Invalid, corrupted, unsupported, or unprocessable files are also returned as `FAILED`.



\---



\## 6. Evidence and Source Information



Where available, extracted fields and line items contain:



\* Page number

\* Evidence/source text



This helps connect structured extraction results back to the original document content.



The extraction system is instructed to use only supplied document text and not external knowledge.



\---



\# 7. Technology Stack



\## Backend



\* Python

\* Flask

\* Flask-SQLAlchemy

\* Flask-Smorest

\* Pydantic

\* Google Gemini API

\* PyMuPDF

\* pytesseract

\* Pillow

\* pypdf



\## Database



SQLite is used for the current implementation.



The database stores:



\* Document name

\* Document type

\* Processing status

\* File type

\* Page count

\* Extracted data

\* Validation results

\* Processing metadata

\* Creation/update timestamps



\## Frontend



The frontend is implemented using:



\* HTML

\* CSS

\* JavaScript



React is not required for this implementation.



\## Testing



Automated tests use:



\* pytest



\---



\# 8. Project Structure



```text

document-intelligence-platform/

│

├── .env.example

├── .gitignore

├── README.md

│

├── backend/

│   ├── requirements.txt

│   ├── pytest.ini

│   │

│   ├── app/

│   │   ├── \_\_init\_\_.py

│   │   ├── main.py

│   │   │

│   │   ├── api/

│   │   │   └── routes/

│   │   │       └── documents.py

│   │   │

│   │   ├── core/

│   │   │   ├── config.py

│   │   │   ├── database.py

│   │   │   └── logging.py

│   │   │

│   │   ├── models/

│   │   │   └── document.py

│   │   │

│   │   ├── schemas/

│   │   │   ├── document.py

│   │   │   └── extraction.py

│   │   │

│   │   ├── services/

│   │   │   ├── document\_validation\_service.py

│   │   │   ├── ocr\_service.py

│   │   │   ├── extraction\_service.py

│   │   │   ├── financial\_validation\_service.py

│   │   │   └── document\_service.py

│   │   │

│   │   ├── repositories/

│   │   │   └── document\_repository.py

│   │   │

│   │   └── utils/

│   │

│   └── tests/

│       ├── test\_api.py

│       ├── test\_extraction.py

│       ├── test\_financial\_validation.py

│       └── test\_validation.py

│

├── frontend/

│   ├── templates/

│   │   └── dashboard.html

│   │

│   └── static/

│       ├── css/

│       │   └── style.css

│       └── js/

│           └── dashboard.js

│

├── docs/

│

└── sample\_outputs/

&#x20;   ├── balance\_sheet.json

&#x20;   ├── cash\_flow\_statement.json

&#x20;   ├── invoice.json

&#x20;   ├── invoice\_validation\_failure.json

&#x20;   └── profit\_and\_loss.json

```



\---



\# 9. Local Setup



\## Prerequisites



Install:



\* Python 3.x

\* Tesseract OCR



Tesseract must be available to the Python OCR service.



\---



\## Clone the repository



```bash

git clone <YOUR\_GITHUB\_REPOSITORY\_URL>

cd document-intelligence-platform

```



\---



\## Create a virtual environment



Windows:



```cmd

python -m venv venv

```



Activate it:



```cmd

venv\\Scripts\\activate

```



\---



\## Install dependencies



```cmd

cd backend

pip install -r requirements.txt

```



\---



\# 10. Environment Variables



Create a `.env` file in the project root.



Example:



```env

SECRET\_KEY=your-secret-key

DATABASE\_URL=sqlite:///document\_intelligence.db



TESSERACT\_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe



GEMINI\_API\_KEY=your-gemini-api-key

GEMINI\_MODEL=your-gemini-model

```



The repository contains `.env.example` as a template.



The actual `.env` file must not be committed to GitHub.



\---



\# 11. Running the Application



From the backend directory:



```cmd

python -m app.main

```



The local application will be available at:



```text

http://127.0.0.1:5000

```



The dashboard is served from the Flask application.



\---



\# 12. API Endpoints



\## Health Check



```http

GET /api/v1/health

```



Example:



```bash

curl http://127.0.0.1:5000/api/v1/health

```



\---



\## Process Document



```http

POST /api/v1/documents/process

```



Content type:



```text

multipart/form-data

```



Parameters:



```text

file

document\_type

```



Example:



```bash

curl -X POST \\

&#x20; -F "file=@invoice.pdf" \\

&#x20; -F "document\_type=invoice" \\

&#x20; http://127.0.0.1:5000/api/v1/documents/process

```



Supported document types:



```text

invoice

balance\_sheet

profit\_and\_loss

cash\_flow\_statement

```



\---



\## Get Latest Document Result



```http

GET /api/v1/documents/{document\_name}

```



Example:



```bash

curl http://127.0.0.1:5000/api/v1/documents/invoice.pdf

```



The latest stored processing result for the requested document name is returned.



\---



\## List Processed Documents



```http

GET /api/v1/documents

```



Example:



```bash

curl http://127.0.0.1:5000/api/v1/documents

```



\---



\# 13. Swagger / OpenAPI



The application exposes API documentation through Swagger UI.



Local URL:



```text

http://127.0.0.1:5000/swagger-ui

```



The Swagger interface can be used to test the API endpoints, including multipart document upload.



\---



\# 14. Response Structure



A successful processing response contains information such as:



```json

{

&#x20; "document\_name": "invoice.pdf",

&#x20; "document\_type": "invoice",

&#x20; "processing\_status": "PASS",

&#x20; "file\_validation": {},

&#x20; "extracted\_data": {},

&#x20; "validation": {},

&#x20; "processing\_metadata": {}

}

```



The exact extracted data depends on the contents of the uploaded document.



\---



\# 15. Sample Outputs



Real processing results are included in:



```text

sample\_outputs/

```



The examples cover:



\* Balance Sheet

\* Cash Flow Statement

\* Profit \& Loss

\* Successful Invoice

\* Financial Validation Failure



The failed invoice example demonstrates that the system reports a genuine financial inconsistency instead of modifying the result to force a pass.



\---



\# 16. Database Persistence



The application uses SQLAlchemy with SQLite.



Processed results are stored in the database after processing.



Stored information includes:



```text

document\_name

document\_type

processing\_status

file\_type

page\_count

extracted\_data

validation\_result

processing\_metadata

created\_at

updated\_at

```



The GET endpoints retrieve persisted processing results rather than requiring the document to be processed again.



\---



\# 17. Automated Testing



The project includes automated tests for:



\### Document validation



Tests cover:



\* Supported file types

\* Unsupported files

\* Empty files

\* Corrupted files

\* File type mismatch

\* PDF validation

\* Image validation

\* Page limits



\### Financial validation



Tests cover:



\* Invoice PASS

\* Invoice FAIL

\* Balance Sheet PASS

\* Balance Sheet FAIL

\* Profit \& Loss PASS

\* Missing financial fields

\* Cash Flow PASS

\* Cash Flow FAIL



\### Extraction



Tests cover:



\* Page preservation

\* Prompt construction

\* API-key configuration

\* Unsupported document types

\* Empty extraction input

\* Structured extraction

\* Evidence/page information

\* Empty AI response

\* Invalid structured AI response



\### API



Tests cover:



\* Health endpoint

\* Document listing

\* Document retrieval

\* Unsupported file upload

\* Missing file

\* Missing document type

\* Invalid document type



Run all tests with:



```cmd

pytest -v

```



The current automated test suite contains 33 passing tests.



\---



\# 18. OCR / AI Model



\## OCR



Tesseract OCR is used for scanned/image documents and PDF pages where native text extraction is not usable.



The application attempts native PDF extraction before falling back to OCR.



\## AI Model



Google Gemini is used for structured financial document extraction.



The model is configured through:



```env

GEMINI\_MODEL=...

```



The API key is configured through:



```env

GEMINI\_API\_KEY=...

```



The extraction response is constrained using a Pydantic structured schema.



\---



\# 19. Confidence



The extraction schema supports evidence and page information.



The current implementation does not depend on a separate numerical confidence score for determining financial correctness.



Financial correctness is determined through deterministic validation rules after extraction.



\---



\# 20. Security Considerations



The project follows basic security practices appropriate for the case study:



\* API credentials are stored in environment variables.

\* `.env` is excluded from Git.

\* Uploaded files are validated before extraction.

\* Unsupported file types are rejected.

\* Corrupted files are rejected.

\* File page count is restricted.

\* Temporary uploaded files are cleaned up after processing.

\* AI extraction is instructed to use only supplied document content.



Secrets must never be committed to the public repository.



\---



\# 21. Deployment



The final submission should expose:



\* Public frontend URL

\* Public backend API URL

\* Public Swagger URL

\* Public health endpoint

\* Public GitHub repository



The deployed frontend must communicate with the deployed backend API rather than assuming a localhost backend.



Deployment URLs will be added here after deployment.



```text

Frontend:

<DEPLOYED\_FRONTEND\_URL>



Backend API:

<DEPLOYED\_BACKEND\_URL>



Swagger:

<DEPLOYED\_SWAGGER\_URL>



Health:

<DEPLOYED\_HEALTH\_URL>



GitHub:

<PUBLIC\_GITHUB\_REPOSITORY\_URL>

```



\---



\# 22. Limitations



This implementation is designed for the internship case study and is not intended to be a full enterprise document-processing platform.



Current limitations include:



\* SQLite is used for persistence.

\* Processing is synchronous.

\* OCR quality depends on document image quality and Tesseract performance.

\* Gemini extraction depends on external API availability and configured API limits.

\* The system supports the four required financial document categories.

\* The application supports documents up to 3 pages as required by the case study.

\* Highly complex document layouts may require additional specialized table extraction techniques.

\* Numerical validation depends on the required financial fields being successfully extracted.



\---



\# 23. Production Improvements



For a production-scale system, possible improvements include:



\* PostgreSQL or another production database

\* Object storage for uploaded documents

\* Background processing queues

\* Retry mechanisms for external AI/OCR services

\* Authentication and authorization

\* Rate limiting

\* Stronger file scanning and malware protection

\* More extensive monitoring and observability

\* Centralized logging

\* Improved table/layout extraction

\* Human review workflows for low-confidence results

\* Horizontal scaling

\* Containerized deployment

\* More comprehensive integration and load testing



These improvements are outside the core scope of the internship case study.



\---



\# 24. AI Assistant Declaration



AI assistants were used during development as development support.



They were used for:



\* Code generation assistance

\* Debugging assistance

\* Test generation

\* Documentation drafting

\* Reviewing implementation structure

\* Troubleshooting development errors



The final implementation was tested against the application's actual behavior, including document processing, OCR, extraction, financial validation, API behavior, database persistence, and automated tests.



The candidate should be able to explain and modify the implementation during the technical discussion/presentation.



\---



\# 25. Case Study Completion



The implementation covers the required end-to-end flow:



```text

Upload

&#x20; ↓

Validation

&#x20; ↓

OCR / Native Text Extraction

&#x20; ↓

Gemini Structured Extraction

&#x20; ↓

Financial Validation

&#x20; ↓

PASS / FAILED

&#x20; ↓

Database Persistence

&#x20; ↓

REST API

&#x20; ↓

Dashboard

```



The project supports:



\* PDF/JPG/PNG input

\* Native and scanned documents

\* Four required document categories

\* Structured extraction

\* Financial calculation validation

\* Evidence/page information

\* Database persistence

\* REST API

\* Swagger/OpenAPI

\* Frontend dashboard

\* Automated testing

\* Sample JSON outputs



\---



\## Author



AI Engineer Internship Technical Case Study



Document Intelligence Platform





