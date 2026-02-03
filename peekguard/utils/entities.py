PRESIDIO_ENTITIES = [
    # Existing
    "PERSON",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "PHONE_NUMBER",
    "US_SSN",
    "IP_ADDRESS",
    "URL",
    "LOCATION",

    # New DLP-backed abstract entities
    "GOVERNMENT_ID",
    "FINANCIAL_ID",
    "TECHNICAL_ID",
    "MEDICAL_ID",
    "SECURITY_DATA",
    "VEHICLE_ID",
    "DEMOGRAPHIC_DATA",
]

PRESIDIO_TO_DLP = {
    "PERSON": ["PERSON_NAME"],
    "EMAIL_ADDRESS": ["EMAIL_ADDRESS"],
    "CREDIT_CARD": ["CREDIT_CARD_DATA"],
    "PHONE_NUMBER": ["PHONE_NUMBER"],
    "US_SSN": ["GOVERNMENT_ID"],
    "IP_ADDRESS": ["TECHNICAL_ID"],
    "URL": ["URL"],
    "LOCATION": ["GEOGRAPHIC_DATA"],

    # New abstract entities
    "GOVERNMENT_ID": ["GOVERNMENT_ID", "PASSPORT", "DRIVERS_LICENSE_NUMBER"],
    "FINANCIAL_ID": ["FINANCIAL_ID"],
    "TECHNICAL_ID": ["TECHNICAL_ID", "MAC_ADDRESS"],
    "MEDICAL_ID": ["MEDICAL_ID", "MEDICAL_DATA"],
    "SECURITY_DATA": ["SECURITY_DATA"],
    "VEHICLE_ID": ["VEHICLE_IDENTIFICATION_NUMBER"],
    "DEMOGRAPHIC_DATA": ["DEMOGRAPHIC_DATA"]
}

# Reverse mapping for converting DLP results back to Presidio entities
DLP_TO_PRESIDIO = {
    dlp: presidio
    for presidio, dlps in PRESIDIO_TO_DLP.items()
    for dlp in dlps
}