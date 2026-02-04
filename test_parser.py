from utils.parser import SAPDocumentParser

# Your exact OCR output
test_text = """Supplier ~ veeese No. Primary ™ -@
Neme Acree Associates 'Status Open
Contact Person -» Sarah Keel ve Posting Dube 27.01.26
'Supplier Raf. No. Osivery Dete 27.01.26
Loca Currency Vv Document Date 27.01.26
Deern/Service Type Rem Sunmary Type Ho Summary
® Type Gam No. Gam Deecription Quarily Open Qty Und Price Dmcount % Price after Dis... GST Code Tomi(ic) 7
A v .. £00001 = ).8. Officaprant 1420 5 5 AUD 500.000 0.00 AUD 500.000 P1 'Y AUD 2,500.000 =
2 nd 0.00 PL
buyer James Chan ve Total Bafore Discount AUD 2,500.08
Owner -_ Chan, Jernes Discount *
Freight -_
Royrdng
Tx AUD 258.008
' Total Payment Due AUD 2,750.000
Remarks"""

parser = SAPDocumentParser()
result = parser.parse_document(test_text)

print("\n" + "="*60)
print("PARSING RESULT:")
print("="*60)
import json
print(json.dumps(result, indent=2))
