"""Populate authoritative ISO world country catalogue for SMS Nations.

Revision ID: 20260903_0016
Revises: 20260902_0015
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260903_0016"
down_revision = "20260902_0015"
branch_labels = None
depends_on = None


COUNTRIES = [
    ('AD', 'AND', 'Andorra', None),
    ('AE', 'ARE', 'United Arab Emirates', None),
    ('AF', 'AFG', 'Afghanistan', None),
    ('AG', 'ATG', 'Antigua and Barbuda', None),
    ('AI', 'AIA', 'Anguilla', None),
    ('AL', 'ALB', 'Albania', None),
    ('AM', 'ARM', 'Armenia', None),
    ('AO', 'AGO', 'Angola', 'AF'),
    ('AQ', 'ATA', 'Antarctica', None),
    ('AR', 'ARG', 'Argentina', None),
    ('AS', 'ASM', 'American Samoa', None),
    ('AT', 'AUT', 'Austria', None),
    ('AU', 'AUS', 'Australia', None),
    ('AW', 'ABW', 'Aruba', None),
    ('AX', 'ALA', 'Åland Islands', None),
    ('AZ', 'AZE', 'Azerbaijan', None),
    ('BA', 'BIH', 'Bosnia and Herzegovina', None),
    ('BB', 'BRB', 'Barbados', None),
    ('BD', 'BGD', 'Bangladesh', None),
    ('BE', 'BEL', 'Belgium', None),
    ('BF', 'BFA', 'Burkina Faso', 'AF'),
    ('BG', 'BGR', 'Bulgaria', None),
    ('BH', 'BHR', 'Bahrain', None),
    ('BI', 'BDI', 'Burundi', 'AF'),
    ('BJ', 'BEN', 'Benin', 'AF'),
    ('BL', 'BLM', 'Saint Barthélemy', None),
    ('BM', 'BMU', 'Bermuda', None),
    ('BN', 'BRN', 'Brunei Darussalam', None),
    ('BO', 'BOL', 'Bolivia, Plurinational State of', None),
    ('BQ', 'BES', 'Bonaire, Sint Eustatius and Saba', None),
    ('BR', 'BRA', 'Brazil', None),
    ('BS', 'BHS', 'Bahamas', None),
    ('BT', 'BTN', 'Bhutan', None),
    ('BV', 'BVT', 'Bouvet Island', None),
    ('BW', 'BWA', 'Botswana', 'AF'),
    ('BY', 'BLR', 'Belarus', None),
    ('BZ', 'BLZ', 'Belize', None),
    ('CA', 'CAN', 'Canada', None),
    ('CC', 'CCK', 'Cocos (Keeling) Islands', None),
    ('CD', 'COD', 'Congo, The Democratic Republic of the', 'AF'),
    ('CF', 'CAF', 'Central African Republic', 'AF'),
    ('CG', 'COG', 'Congo', 'AF'),
    ('CH', 'CHE', 'Switzerland', None),
    ('CI', 'CIV', "Côte d'Ivoire", 'AF'),
    ('CK', 'COK', 'Cook Islands', None),
    ('CL', 'CHL', 'Chile', None),
    ('CM', 'CMR', 'Cameroon', 'AF'),
    ('CN', 'CHN', 'China', None),
    ('CO', 'COL', 'Colombia', None),
    ('CR', 'CRI', 'Costa Rica', None),
    ('CU', 'CUB', 'Cuba', None),
    ('CV', 'CPV', 'Cabo Verde', 'AF'),
    ('CW', 'CUW', 'Curaçao', None),
    ('CX', 'CXR', 'Christmas Island', None),
    ('CY', 'CYP', 'Cyprus', None),
    ('CZ', 'CZE', 'Czechia', None),
    ('DE', 'DEU', 'Germany', None),
    ('DJ', 'DJI', 'Djibouti', 'AF'),
    ('DK', 'DNK', 'Denmark', None),
    ('DM', 'DMA', 'Dominica', None),
    ('DO', 'DOM', 'Dominican Republic', None),
    ('DZ', 'DZA', 'Algeria', 'AF'),
    ('EC', 'ECU', 'Ecuador', None),
    ('EE', 'EST', 'Estonia', None),
    ('EG', 'EGY', 'Egypt', 'AF'),
    ('EH', 'ESH', 'Western Sahara', None),
    ('ER', 'ERI', 'Eritrea', 'AF'),
    ('ES', 'ESP', 'Spain', None),
    ('ET', 'ETH', 'Ethiopia', 'AF'),
    ('FI', 'FIN', 'Finland', None),
    ('FJ', 'FJI', 'Fiji', None),
    ('FK', 'FLK', 'Falkland Islands (Malvinas)', None),
    ('FM', 'FSM', 'Micronesia, Federated States of', None),
    ('FO', 'FRO', 'Faroe Islands', None),
    ('FR', 'FRA', 'France', None),
    ('GA', 'GAB', 'Gabon', 'AF'),
    ('GB', 'GBR', 'United Kingdom', None),
    ('GD', 'GRD', 'Grenada', None),
    ('GE', 'GEO', 'Georgia', None),
    ('GF', 'GUF', 'French Guiana', None),
    ('GG', 'GGY', 'Guernsey', None),
    ('GH', 'GHA', 'Ghana', 'AF'),
    ('GI', 'GIB', 'Gibraltar', None),
    ('GL', 'GRL', 'Greenland', None),
    ('GM', 'GMB', 'Gambia', 'AF'),
    ('GN', 'GIN', 'Guinea', 'AF'),
    ('GP', 'GLP', 'Guadeloupe', None),
    ('GQ', 'GNQ', 'Equatorial Guinea', 'AF'),
    ('GR', 'GRC', 'Greece', None),
    ('GS', 'SGS', 'South Georgia and the South Sandwich Islands', None),
    ('GT', 'GTM', 'Guatemala', None),
    ('GU', 'GUM', 'Guam', None),
    ('GW', 'GNB', 'Guinea-Bissau', 'AF'),
    ('GY', 'GUY', 'Guyana', None),
    ('HK', 'HKG', 'Hong Kong', None),
    ('HM', 'HMD', 'Heard Island and McDonald Islands', None),
    ('HN', 'HND', 'Honduras', None),
    ('HR', 'HRV', 'Croatia', None),
    ('HT', 'HTI', 'Haiti', None),
    ('HU', 'HUN', 'Hungary', None),
    ('ID', 'IDN', 'Indonesia', None),
    ('IE', 'IRL', 'Ireland', None),
    ('IL', 'ISR', 'Israel', None),
    ('IM', 'IMN', 'Isle of Man', None),
    ('IN', 'IND', 'India', None),
    ('IO', 'IOT', 'British Indian Ocean Territory', None),
    ('IQ', 'IRQ', 'Iraq', None),
    ('IR', 'IRN', 'Iran, Islamic Republic of', None),
    ('IS', 'ISL', 'Iceland', None),
    ('IT', 'ITA', 'Italy', None),
    ('JE', 'JEY', 'Jersey', None),
    ('JM', 'JAM', 'Jamaica', None),
    ('JO', 'JOR', 'Jordan', None),
    ('JP', 'JPN', 'Japan', None),
    ('KE', 'KEN', 'Kenya', 'AF'),
    ('KG', 'KGZ', 'Kyrgyzstan', None),
    ('KH', 'KHM', 'Cambodia', None),
    ('KI', 'KIR', 'Kiribati', None),
    ('KM', 'COM', 'Comoros', 'AF'),
    ('KN', 'KNA', 'Saint Kitts and Nevis', None),
    ('KP', 'PRK', "Korea, Democratic People's Republic of", None),
    ('KR', 'KOR', 'Korea, Republic of', None),
    ('KW', 'KWT', 'Kuwait', None),
    ('KY', 'CYM', 'Cayman Islands', None),
    ('KZ', 'KAZ', 'Kazakhstan', None),
    ('LA', 'LAO', "Lao People's Democratic Republic", None),
    ('LB', 'LBN', 'Lebanon', None),
    ('LC', 'LCA', 'Saint Lucia', None),
    ('LI', 'LIE', 'Liechtenstein', None),
    ('LK', 'LKA', 'Sri Lanka', None),
    ('LR', 'LBR', 'Liberia', 'AF'),
    ('LS', 'LSO', 'Lesotho', 'AF'),
    ('LT', 'LTU', 'Lithuania', None),
    ('LU', 'LUX', 'Luxembourg', None),
    ('LV', 'LVA', 'Latvia', None),
    ('LY', 'LBY', 'Libya', 'AF'),
    ('MA', 'MAR', 'Morocco', 'AF'),
    ('MC', 'MCO', 'Monaco', None),
    ('MD', 'MDA', 'Moldova, Republic of', None),
    ('ME', 'MNE', 'Montenegro', None),
    ('MF', 'MAF', 'Saint Martin (French part)', None),
    ('MG', 'MDG', 'Madagascar', 'AF'),
    ('MH', 'MHL', 'Marshall Islands', None),
    ('MK', 'MKD', 'North Macedonia', None),
    ('ML', 'MLI', 'Mali', 'AF'),
    ('MM', 'MMR', 'Myanmar', None),
    ('MN', 'MNG', 'Mongolia', None),
    ('MO', 'MAC', 'Macao', None),
    ('MP', 'MNP', 'Northern Mariana Islands', None),
    ('MQ', 'MTQ', 'Martinique', None),
    ('MR', 'MRT', 'Mauritania', 'AF'),
    ('MS', 'MSR', 'Montserrat', None),
    ('MT', 'MLT', 'Malta', None),
    ('MU', 'MUS', 'Mauritius', 'AF'),
    ('MV', 'MDV', 'Maldives', None),
    ('MW', 'MWI', 'Malawi', 'AF'),
    ('MX', 'MEX', 'Mexico', None),
    ('MY', 'MYS', 'Malaysia', None),
    ('MZ', 'MOZ', 'Mozambique', 'AF'),
    ('NA', 'NAM', 'Namibia', 'AF'),
    ('NC', 'NCL', 'New Caledonia', None),
    ('NE', 'NER', 'Niger', 'AF'),
    ('NF', 'NFK', 'Norfolk Island', None),
    ('NG', 'NGA', 'Nigeria', 'AF'),
    ('NI', 'NIC', 'Nicaragua', None),
    ('NL', 'NLD', 'Netherlands', None),
    ('NO', 'NOR', 'Norway', None),
    ('NP', 'NPL', 'Nepal', None),
    ('NR', 'NRU', 'Nauru', None),
    ('NU', 'NIU', 'Niue', None),
    ('NZ', 'NZL', 'New Zealand', None),
    ('OM', 'OMN', 'Oman', None),
    ('PA', 'PAN', 'Panama', None),
    ('PE', 'PER', 'Peru', None),
    ('PF', 'PYF', 'French Polynesia', None),
    ('PG', 'PNG', 'Papua New Guinea', None),
    ('PH', 'PHL', 'Philippines', None),
    ('PK', 'PAK', 'Pakistan', None),
    ('PL', 'POL', 'Poland', None),
    ('PM', 'SPM', 'Saint Pierre and Miquelon', None),
    ('PN', 'PCN', 'Pitcairn', None),
    ('PR', 'PRI', 'Puerto Rico', None),
    ('PS', 'PSE', 'Palestine, State of', None),
    ('PT', 'PRT', 'Portugal', None),
    ('PW', 'PLW', 'Palau', None),
    ('PY', 'PRY', 'Paraguay', None),
    ('QA', 'QAT', 'Qatar', None),
    ('RE', 'REU', 'Réunion', None),
    ('RO', 'ROU', 'Romania', None),
    ('RS', 'SRB', 'Serbia', None),
    ('RU', 'RUS', 'Russian Federation', None),
    ('RW', 'RWA', 'Rwanda', 'AF'),
    ('SA', 'SAU', 'Saudi Arabia', None),
    ('SB', 'SLB', 'Solomon Islands', None),
    ('SC', 'SYC', 'Seychelles', 'AF'),
    ('SD', 'SDN', 'Sudan', 'AF'),
    ('SE', 'SWE', 'Sweden', None),
    ('SG', 'SGP', 'Singapore', None),
    ('SH', 'SHN', 'Saint Helena, Ascension and Tristan da Cunha', None),
    ('SI', 'SVN', 'Slovenia', None),
    ('SJ', 'SJM', 'Svalbard and Jan Mayen', None),
    ('SK', 'SVK', 'Slovakia', None),
    ('SL', 'SLE', 'Sierra Leone', 'AF'),
    ('SM', 'SMR', 'San Marino', None),
    ('SN', 'SEN', 'Senegal', 'AF'),
    ('SO', 'SOM', 'Somalia', 'AF'),
    ('SR', 'SUR', 'Suriname', None),
    ('SS', 'SSD', 'South Sudan', 'AF'),
    ('ST', 'STP', 'Sao Tome and Principe', 'AF'),
    ('SV', 'SLV', 'El Salvador', None),
    ('SX', 'SXM', 'Sint Maarten (Dutch part)', None),
    ('SY', 'SYR', 'Syrian Arab Republic', None),
    ('SZ', 'SWZ', 'Eswatini', 'AF'),
    ('TC', 'TCA', 'Turks and Caicos Islands', None),
    ('TD', 'TCD', 'Chad', 'AF'),
    ('TF', 'ATF', 'French Southern Territories', None),
    ('TG', 'TGO', 'Togo', 'AF'),
    ('TH', 'THA', 'Thailand', None),
    ('TJ', 'TJK', 'Tajikistan', None),
    ('TK', 'TKL', 'Tokelau', None),
    ('TL', 'TLS', 'Timor-Leste', None),
    ('TM', 'TKM', 'Turkmenistan', None),
    ('TN', 'TUN', 'Tunisia', 'AF'),
    ('TO', 'TON', 'Tonga', None),
    ('TR', 'TUR', 'Türkiye', None),
    ('TT', 'TTO', 'Trinidad and Tobago', None),
    ('TV', 'TUV', 'Tuvalu', None),
    ('TW', 'TWN', 'Taiwan, Province of China', None),
    ('TZ', 'TZA', 'Tanzania, United Republic of', 'AF'),
    ('UA', 'UKR', 'Ukraine', None),
    ('UG', 'UGA', 'Uganda', 'AF'),
    ('UM', 'UMI', 'United States Minor Outlying Islands', None),
    ('US', 'USA', 'United States', None),
    ('UY', 'URY', 'Uruguay', None),
    ('UZ', 'UZB', 'Uzbekistan', None),
    ('VA', 'VAT', 'Holy See (Vatican City State)', None),
    ('VC', 'VCT', 'Saint Vincent and the Grenadines', None),
    ('VE', 'VEN', 'Venezuela, Bolivarian Republic of', None),
    ('VG', 'VGB', 'Virgin Islands, British', None),
    ('VI', 'VIR', 'Virgin Islands, U.S.', None),
    ('VN', 'VNM', 'Viet Nam', None),
    ('VU', 'VUT', 'Vanuatu', None),
    ('WF', 'WLF', 'Wallis and Futuna', None),
    ('WS', 'WSM', 'Samoa', None),
    ('YE', 'YEM', 'Yemen', None),
    ('YT', 'MYT', 'Mayotte', None),
    ('ZA', 'ZAF', 'South Africa', 'AF'),
    ('ZM', 'ZMB', 'Zambia', 'AF'),
    ('ZW', 'ZWE', 'Zimbabwe', 'AF')
]


def country_uuid(iso2: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"sms-country:{iso2}")


def upgrade() -> None:
    connection = op.get_bind()

    for iso2, iso3, name, continent_code in COUNTRIES:
        existing = connection.execute(
            sa.text(
                "SELECT id FROM countries WHERE iso2 = :iso2"
            ),
            {"iso2": iso2},
        ).fetchone()

        if existing:
            connection.execute(
                sa.text(
                    """
                    UPDATE countries
                    SET iso3 = :iso3,
                        name = :name,
                        continent_code = :continent_code,
                        is_active = true
                    WHERE iso2 = :iso2
                    """
                ),
                {
                    "iso2": iso2,
                    "iso3": iso3,
                    "name": name,
                    "continent_code": continent_code,
                },
            )
        else:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO countries (
                        id,
                        iso2,
                        iso3,
                        name,
                        continent_code,
                        is_active
                    )
                    VALUES (
                        :id,
                        :iso2,
                        :iso3,
                        :name,
                        :continent_code,
                        true
                    )
                    """
                ),
                {
                    "id": country_uuid(iso2),
                    "iso2": iso2,
                    "iso3": iso3,
                    "name": name,
                    "continent_code": continent_code,
                },
            )

    connection.execute(
        sa.text(
            """
            UPDATE countries
            SET is_active = false
            WHERE iso2 NOT IN :iso2_codes
            """
        ).bindparams(
            sa.bindparam(
                "iso2_codes",
                expanding=True,
            )
        ),
        {"iso2_codes": [row[0] for row in COUNTRIES]},
    )


def downgrade() -> None:
    # Preserve country rows because athlete residence/eligibility FKs may refer to them.
    # Downgrade only deactivates rows introduced outside the former 89-country catalogue.
    former_iso2 = {
        "DZ","AO","BJ","BW","BF","BI","CV","CM","CF","TD","KM","CG","CD","CI",
        "DJ","EG","GQ","ER","SZ","ET","GA","GM","GH","GN","GW","KE","LS","LR",
        "LY","MG","MW","ML","MR","MU","MA","MZ","NA","NE","NG","RW","ST","SN",
        "SC","SL","SO","ZA","SS","SD","TZ","TG","TN","UG","ZM","ZW",
        "FR","GB","DE","IT","ES","PT","BE","NL","CH","AT","IE","SE","NO","DK",
        "FI","PL","GR","TR","US","CA","MX","BR","AR","CO","CL","UY","SA","AE",
        "QA","JP","KR","CN","IN","AU","NZ"
    }

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE countries
            SET is_active = false
            WHERE iso2 NOT IN :iso2_codes
            """
        ).bindparams(
            sa.bindparam(
                "iso2_codes",
                expanding=True,
            )
        ),
        {"iso2_codes": sorted(former_iso2)},
    )
