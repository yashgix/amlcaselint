# Data terms

- FinCEN enforcement-action PDFs (https://www.fincen.gov/news/enforcement-actions), fetched 14 Nov 2026. FinCEN's
  site policy (https://www.fincen.gov/site-policies-and-notices, read 14 Nov 2026) says: "This website is provided as
  a public service and is considered public information, which may be distributed or copied in accordance with
  applicable law. Use of appropriate byline/photo/image credits is requested." The orders are works of the US federal
  government, which have no US copyright (17 U.S.C. 105). Credit: Financial Crimes Enforcement Network, US Department
  of the Treasury.
- 31 CFR 1020.320 as published by the eCFR (https://www.ecfr.gov/api/versioner/v1/full/2026-11-01/title-31.xml?part=1020&section=1020.320),
  fetched 14 Nov 2026; federal regulation text, a US government work.
- orders/*.txt: text extracted from those PDFs with pdftotext 26.09.0 (Poppler), default mode, `-enc UTF-8`, unedited.
- gold.json: labels made for this project from the pinned text (see its labeller and method fields).
