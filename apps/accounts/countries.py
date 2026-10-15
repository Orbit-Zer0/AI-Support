COUNTRY_CHOICES = [
    ('KG', 'Kyrgyzstan'),
    ('KZ', 'Kazakhstan'),
    ('RU', 'Russia'),
    ('UZ', 'Uzbekistan'),
    ('TJ', 'Tajikistan'),
    ('TM', 'Turkmenistan'),
    ('AZ', 'Azerbaijan'),
    ('AM', 'Armenia'),
    ('GE', 'Georgia'),
    ('BY', 'Belarus'),
    ('MD', 'Moldova'),
    ('UA', 'Ukrain'),
]

ALLOWED_COUNTRIES = {code for code, _ in COUNTRY_CHOICES}