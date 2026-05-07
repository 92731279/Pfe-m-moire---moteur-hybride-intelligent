import xml.etree.ElementTree as ET

def clean_address(input_xml):
    """
    Clean redundant information in the AdrLine field of the XML document.
    """
    tree = ET.ElementTree(ET.fromstring(input_xml))
    root = tree.getroot()

    # Navigate to the relevant fields
    for cdt_trf in root.findall(".//CdtTrfTxInf"):
        debtor = cdt_trf.find("Dbtr")
        if debtor is not None:
            postal_address = debtor.find("PstlAdr")
            if postal_address is not None:
                adr_line = postal_address.find("AdrLine")
                post_box = postal_address.find("PstBx")
                town_name = postal_address.find("TwnNm")
                country = postal_address.find("Ctry")

                if adr_line is not None:
                    # Debug logs
                    print(f"Original AdrLine: {adr_line.text}")

                    # Clear AdrLine if its components are already classified
                    adr_line_text = adr_line.text
                    classified_components = []

                    if post_box is not None:
                        classified_components.append(post_box.text)
                    if town_name is not None:
                        classified_components.append(town_name.text)
                    if country is not None:
                        classified_components.append(country.text)

                    for component in classified_components:
                        if component in adr_line_text:
                            adr_line_text = adr_line_text.replace(component, "").strip()

                    # If AdrLine is empty after removing classified components, clear it
                    adr_line.text = adr_line_text if adr_line_text.strip() else None

                    # Debug logs after modification
                    print(f"Modified AdrLine: {adr_line.text}")

    # Return the cleaned XML as a string
    return ET.tostring(root, encoding="unicode")

# Example input XML
data = '''<?xml version="1.0" ?>
<Document>
  <FIToFICstmrCdtTrf>
    <CdtTrfTxInf>
      <Dbtr>
        <Nm>MR BEN DJEMAA YASSINE</Nm>
        <PstlAdr>
          <PstBx>BP N 4</PstBx>
          <TwnNm>OUED REMEL</TwnNm>
          <Ctry>TN</Ctry>
          <AdrLine>BP N 4 WED RMAL SFAX</AdrLine>
        </PstlAdr>
        <CtryOfRes>TN</CtryOfRes>
      </Dbtr>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>'''

# Clean the address
cleaned_data = clean_address(data)
print(cleaned_data)