from src.privacy.pii_masker import detect_pii_counts, mask_dataframe, mask_text

def test_email_is_masked():
    assert mask_text("email fake.student@example.com now") == "email [EMAIL REMOVED] now"

def test_phone_is_masked():
    assert "[PHONE REMOVED]" in mask_text("Phone 0412 345 678 please")

def test_url_is_masked():
    assert mask_text("See https://example.invalid/private") == "See [URL REMOVED]"

def test_dataframe_masks_before_analysis(golden_df):
    masked, changes = mask_dataframe(golden_df)
    assert changes == 1
    assert "example.com" not in " ".join(masked["AdditionalComments"].dropna())

def test_detection_counts_patterns_without_values(golden_df):
    counts = detect_pii_counts(golden_df)
    assert counts == {"emails": 1, "phones": 0, "urls": 0}
