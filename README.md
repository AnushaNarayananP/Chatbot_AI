Model chosen and why

We used nvidia/nemotron-nano-12b-v2-vl:free through OpenRouter as the vision model for image-based tasks. This model was chosen because it supports multimodal input, meaning it can process both text and images in the same request. That makes it suitable for the main use cases in this project: OCR-style text extraction, image description, and question answering from images.

It was also a practical choice because it was available through an API-based workflow, which matched the project requirement of using a Vision LLM via OpenRouter instead of running a model locally. This helped keep the system modular: text-only chats continue through the existing Ollama pipeline, while image-based requests are routed to the vision model.

API structure

The system uses two separate flows:

1. Text-only flow
User sends only text
Request is handled by the existing Ollama text chatbot
Response is returned as normal conversational chat
2. Vision flow
User provides:
an uploaded image, or
an image URL
The system builds a multimodal request containing:
the user’s text instruction
the image
This request is sent to the OpenRouter API
The model returns a text response, which is then processed by the chatbot pipeline
Request logic

The vision request contains:

user intent from the prompt
Example: “What is written on this bill?”
image data
either image URL
or encoded uploaded image
task guidance
OCR
captioning
visual Q&A
general image understanding
Response logic

The response is processed into:

raw answer text
task-specific interpretation where possible, such as:
extracted text
caption
direct answer to user question
short summary
Limitations

This system has a few practical limitations:

1. Free model availability

Because the selected model is accessed through a free API route, availability may not always be guaranteed. There can be:

slower responses
temporary failures
rate limits
2. OCR accuracy depends on image quality

Text extraction may fail or become incomplete when:

the image is blurry
lighting is poor
text is too small
the document is tilted or partially visible
3. Vision output is not always perfectly structured

The model mainly returns natural language responses. Even when asked for structured extraction, the output can still vary depending on the image and prompt.

4. Limited object reasoning compared to specialized models

The system can answer simple visual questions and describe visible content, but it is not a dedicated object detector. So fine-grained counting, exact localization, or highly detailed classification may be unreliable.

5. User intent affects output quality

The quality of the result depends a lot on the user prompt. Clear prompts like:

“Extract all text from this receipt”
“Describe this image”
“What is the total amount shown here?”

usually work better than vague prompts.

Examples of Input and Output
1. OCR + Structured Extraction

User Input:
What is written in this bill?

Chatbot Output:
Merchant: Gujarat Freight Tools
Total: ₹4,490.00
Key items:

Bosch All-in-One Metal Hand Tool Kit — ₹2,535.00
Taparia Universal Tool Kit — ₹1,270.00

Extracted Text:

Merchant/Store Name: Gujarat Freight Tools
Invoice/Challan Date: 23-Jul-2025
Invoice Amount: ₹4,490.00 (including ₹684.90 GST @18%)
Payment Method: UPI via ICICI Bank
Terms:
“Our Responsibility Ceases as soon as goods leaves our Premises.”
“Goods once sold will not be taken back.”

Summary:
This invoice from Gujarat Freight Tools details two tool kits sold on 23-Jul-2025. The total invoice amount is ₹4,490.00, including ₹684.90 GST @18%. Payment was made via UPI. The invoice also mentions that goods sold will not be taken back.

2. Visual Question Answering

User Input:
What is the total amount?

Chatbot Output:
The total amount is ₹4,490.00, which includes ₹684.90 GST @18%.

3. Image Captioning / Document Description

User Input:
Describe this image.

Chatbot Output:
This image shows a tax invoice from Gujarat Freight Tools, a company dealing in precision press tools and components. The document includes:

Company Name: Gujarat Freight Tools
Invoice No.: 26CORPP3939N1
Date: 23-Jul-2025
Customer: Shiv Engineering, Kochi, Kerala
Transporter: Silver Roadlines
Products Listed:
Bosch All-in-One Metal Hand Tool Kit — ₹2,535.00
Taparia Universal Tool Kit — ₹1,270.00
Tax: IGST @18% = ₹684.90
Total Amount: ₹4,490.00
Payment Section: QR code for UPI payment
Other Details: Bank account information, terms and conditions, and recipient copy marking

Overall, the image is a structured invoice document containing merchant details, customer details, purchased products, tax calculations, payment details, and invoice terms.

