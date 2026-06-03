from fpdf import FPDF

class PurplleGuidePDF(FPDF):
    def header(self):
        # Top brand color bar
        self.set_fill_color(74, 21, 75) # Purplle deep purple #4A154B
        self.rect(0, 0, 210, 8, 'F')
        
        self.ln(10)
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(74, 21, 75)
        self.cell(0, 10, 'PURPLLE STORE INTELLIGENCE', align='C')
        self.ln(6)
        self.set_font('helvetica', 'B', 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, 'SYSTEM DEPLOYMENT & RUN GUIDE', align='C')
        self.ln(15)
        
        # Horizontal rule
        self.set_draw_color(220, 220, 220)
        self.line(15, 35, 195, 35)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Purplle Confidential', align='C')

    def add_section_header(self, title):
        self.ln(5)
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(74, 21, 75)
        self.cell(0, 8, title)
        self.ln(8)
        self.set_text_color(50, 50, 50) # reset to body text color

    def add_body_text(self, text, style=''):
        self.set_font('helvetica', style, 10.5)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def add_code_block(self, command):
        self.set_font('Courier', 'B', 10)
        self.set_fill_color(245, 242, 247) # Light violet-gray background
        self.set_text_color(190, 24, 74) # Purplle secondary pinkish accent for commands
        self.set_draw_color(220, 210, 225)
        
        # Draw code cell
        self.cell(0, 8, f"  {command}", border=1, fill=True)
        self.ln(11)
        self.set_text_color(50, 50, 50) # reset to standard body text color

# Instantiate PDF
pdf = PurplleGuidePDF()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.alias_nb_pages()
pdf.add_page()

# Document Description
pdf.add_body_text("This deployment guide provides instructions for setting up and running the enterprise-grade Purplle Store Intelligence System. The application consists of a FastAPI backend and a Streamlit analytics dashboard panel.")

# Section 1
pdf.add_section_header("1. IMPORTANT: CCTV Video Feeds (Not Uploaded to GitHub)")
pdf.add_body_text("Note on Submission Safety:", 'B')
pdf.add_body_text("Due to GitHub file size limits and data privacy standards, raw CCTV video feeds are NOT included in the GitHub repository. To test or run the computer vision ingestion pipeline, you must manually place your video files (.mp4 or .avi formats) in the following directory:")

# Highlight video path
pdf.set_font('Courier', 'B', 11)
pdf.set_fill_color(255, 243, 205) # Yellow warning highlight
pdf.set_text_color(133, 100, 4)
pdf.set_draw_color(255, 238, 186)
pdf.cell(0, 8, "  data/videos/", border=1, fill=True)
pdf.ln(12)

# Section 2
pdf.add_section_header("2. Local Environment Setup")
pdf.add_body_text("Run the following build command to automatically create the Python virtual environment (.venv) and install all required modules:")
pdf.add_code_block("make setup")

pdf.add_body_text("Once setup completes successfully, activate your environment using the appropriate script for your terminal:")
pdf.add_body_text("On Windows (PowerShell):", 'B')
pdf.add_code_block(r".\.venv\Scripts\activate")
pdf.add_body_text("On macOS / Linux:", 'B')
pdf.add_code_block("source .venv/bin/activate")

# Section 3
pdf.add_section_header("3. Database Ingestion & Seeding")
pdf.add_body_text("Run this command to initialize the schemas and seed the SQLite database with premium mock stores and visitor sessions:")
pdf.add_code_block("make seed")

# Section 4
pdf.add_section_header("4. Running the System")
pdf.add_body_text("To launch the complete application, open two separate terminal sessions and activate the virtual environment in both.")

pdf.add_body_text("Terminal 1: Start the Backend (FastAPI)", 'B')
pdf.add_body_text("Run the API server (available at http://localhost:8000):")
pdf.add_code_block("make run")

pdf.add_body_text("Terminal 2: Start the Dashboard (Streamlit)", 'B')
pdf.add_body_text("Run the analytics dashboard panel (opens at http://localhost:8501):")
pdf.add_code_block("make run-dashboard")

# Section 5
pdf.add_section_header("5. Data Stream Simulation & Video Processing")
pdf.add_body_text("If you want to mock CCTV stream edge vision logs directly to the active API:")
pdf.add_code_block("make stream-mock")

pdf.add_body_text("To run the computer vision edge-processing pipeline directly on the video files placed in data/videos/:")
pdf.add_code_block("python pipeline/main.py")

# Output the file
pdf.output("RUNNING_INSTRUCTIONS.pdf")
print("New PDF created successfully.")
