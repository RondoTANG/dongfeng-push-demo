from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor

def create_slide(filename):
    c = canvas.Canvas(filename, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Background
    c.setFillColor(HexColor("#F9F9FB"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Header Accent
    c.setFillColor(HexColor("#E01E2E")) # Dongfeng Red
    c.rect(40, height - 60, 8, 30, fill=1, stroke=0)
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(HexColor("#111827"))
    c.drawString(60, height - 55, "P1-3 Business Process - Automated Tag Engine")
    
    # Subtitle
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor("#4B5563"))
    c.drawString(60, height - 80, "Data-driven task distribution mapping users' XP directly to elite tags.")
    
    # Left Block: Tag Automation Flow (No more pain points)
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(40, 100, width/2 - 60, height - 220, 10, fill=1, stroke=0)
    
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(HexColor("#111827"))
    c.drawString(70, height - 160, "1. XP-to-Tag Automation")
    
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#6B7280"))
    c.drawString(70, height - 190, "- Daily system calculation of XP thresholds")
    c.drawString(70, height - 215, "- Auto-assign 'Expert' & 'Master' tags")
    c.drawString(70, height - 240, "- Zero manual intervention required")
    
    # Right Block: Distribution Cycle
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(width/2 + 20, 100, width/2 - 60, height - 220, 10, fill=1, stroke=0)
    
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(HexColor("#111827"))
    c.drawString(width/2 + 50, height - 160, "2. Cycle Distribution Engine")
    
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#6B7280"))
    c.drawString(width/2 + 50, height - 190, "- Master Cover Pool (Top Tier)")
    c.drawString(width/2 + 50, height - 215, "- Expert Cover Pool (High Priority)")
    c.drawString(width/2 + 50, height - 240, "- Fair rotation without manual exclusion")
    
    # Bottom accent
    c.setFillColor(HexColor("#E5E7EB"))
    c.rect(40, 40, width - 80, 1, fill=1, stroke=0)
    c.setFont("Helvetica", 9)
    c.drawString(40, 25, "Dongfeng Growth System Architecture v2.0")
    
    c.save()

create_slide("slide_layout_canvas.pdf")
print("PDF Generated!")
