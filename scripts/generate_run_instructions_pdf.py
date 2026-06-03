import os
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        # Set font
        self.set_font('helvetica', 'B', 16)
        # Title
        self.cell(0, 10, 'Purplle Store Intelligence System', align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_font('helvetica', 'I', 11)
        self.cell(0, 6, 'Technical Run Instructions & Deployment Guide', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        # Horizontal line
        self.line(10, 32, 200, 32)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()} | Purplle Store Intelligence System (Tech Challenge 2026)', align='C')

def create_instructions_pdf():
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('helvetica', '', 10)
    
    # 1. Project Overview
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, '1. Project Overview', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('helvetica', '', 10)
    overview_text = (
        "The Purplle Store Intelligence System is an enterprise-grade AI engine designed to "
        "analyze live CCTV video streams, track visitors, compute zone-specific occupancies, "
        "measure queue wait times, and detect behavioral anomalies (such as loitering or "
        "occlusions). The architecture comprises a FastAPI backend for real-time data ingestion "
        "and aggregates, paired with a dynamic Streamlit frontend dashboard."
    )
    pdf.multi_cell(0, 5, overview_text)
    pdf.ln(4)
    
    # 2. Option 1: Live Cloud Demo
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, '2. Option 1: Live Cloud Demo (Instant Review)', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('helvetica', '', 10)
    opt1_text = (
        "For immediate validation, the system is actively running in a containerized environment on Hugging Face Spaces:\n"
        " - Live Dashboard Link: https://siddardha696-purplle-store-intelligence.hf.space\n"
        " - Usage: Open the URL and click the 'Active Live CCTV Feed Stream' toggle to see real-time bounding box annotations and dynamically changing occupancy statistics."
    )
    pdf.multi_cell(0, 5, opt1_text)
    pdf.ln(4)

    # 3. Option 2: Run Locally via Docker
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, '3. Option 2: Run Locally via Docker (Easiest Local Method)', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('helvetica', '', 10)
    opt2_text = (
        "The root directory contains a customized Dockerfile bundling both FastAPI and Streamlit into a single container.\n\n"
        "1. Build the Docker image:\n"
        "   docker build -t purplle-store-intelligence .\n\n"
        "2. Run the Docker container:\n"
        "   docker run -p 7860:7860 -p 8000:8000 purplle-store-intelligence\n\n"
        "3. Access the dashboard:\n"
        "   Open http://localhost:7860 in your web browser."
    )
    pdf.multi_cell(0, 5, opt2_text)
    pdf.ln(4)
    
    # 4. Option 3: Manual Local Run
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, '4. Option 3: Manual Local Run (Python Environment)', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('helvetica', '', 10)
    opt3_text = (
        "To run the services natively on your local machine, ensure you have Python 3.10+ installed, then follow these steps:\n\n"
        "1. Install required packages:\n"
        "   pip install -r requirements.txt\n\n"
        "2. Initialize and seed the SQLite database:\n"
        "   python scripts/init_db.py\n\n"
        "3. Start the FastAPI backend engine (Run in Terminal 1):\n"
        "   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000\n\n"
        "4. Launch the Streamlit dashboard app (Run in Terminal 2):\n"
        "   streamlit run dashboard/app.py --server.port 7860\n\n"
        "5. Preview in Browser:\n"
        "   Navigate to http://localhost:7860."
    )
    pdf.multi_cell(0, 5, opt3_text)
    
    # Save PDF
    pdf_output = "purplle_store_intelligence_instructions.pdf"
    pdf.output(pdf_output)
    print(f"PDF successfully generated at: {os.path.abspath(pdf_output)}")

if __name__ == "__main__":
    create_instructions_pdf()
