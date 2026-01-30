from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)

text = """
PARIS TRAVEL GUIDE 2025

1. HIDDEN GEMS
- The "Petite Ceinture": An abandoned railway line turned into a nature trail. Great for walks away from crowds.
- Musee de la Vie Romantique: A quiet museum with a lovely tea room, perfect for couples.
- Rue Cremieux: A colorful street often called the 'Notting Hill of Paris', great for photos but respect the residents!

2. BUDGET TIPS
- Use the "Navigo Decouverte" pass for unlimited metro travel (approx 30 Euros/week).
- Free Museums: The Petit Palais and Musee Carnavalet are free to enter year-round.
- Cheap Eats: Try 'L'As du Fallafel' in Le Marais for the best falafel under 10 Euros.

3. VISA RULES
- Tourists from many countries don't need a visa for stays under 90 days.
- Ensure your passport is valid for at least 3 months beyond your planned departure.
"""

pdf.multi_cell(0, 10, text)
pdf.output("paris_guide.pdf")
print("✅ paris_guide.pdf created successfully!")