import io

from shadow.extract.declared import read_jar_vilnius, read_sodra
from shadow.load.declared import latest_activity

JAR_SAMPLE = '''ja_kodas|ja_pavadinimas|adresas|ja_reg_data|form_kodas|form_pavadinimas|stat_kodas|stat_pavadinimas|stat_data_nuo|formavimo_data
110379432|"Uždaroji akcinė bendrovė ""Naujasis Vilnius"""|Vilnius, Gedimino pr. 1, LT-01103|1992-03-10|310|Uždaroji akcinė bendrovė|0|Teisinis stat neįregistruotas|1992-03-10|2026-11-20
110004884|"Uždaroji akcinė bendrovė ""VILLON"""|Vilniaus r. sav., Avižienių sen., Ežeraičių k., Ežeraičių g. 2, LT-14200|1991-04-25|310|Uždaroji akcinė bendrovė|0|Teisinis stat neįregistruotas|1991-04-25|2026-11-20
'''

SODRA_SAMPLE = '''Draudėjo kodas (code);Juridinių asmenų registro kodas (jarCode);Pavadinimas (name);Savivaldybė, kurioje registruota(municipality);Ekonominės veiklos rūšies kodas(ecoActCode);Ekonominės veiklos rūšies kodas EVRK(ecoActCodeStr);Ekonominės veiklos rūšies pavadinimas(ecoActName);Mėnuo (month);Vidutinis darbo užmokestis (avgWage);Apdraustųjų skaičius (numInsured);Vidutinis darbo užmokestis II (avgWage2);Apdraustųjų skaičius II (numInsured2);Valstybinio socialinio draudimo įmoka (tax)
41055;110379432;"UŽDAROJI AKCINĖ BENDROVĖ ""NAUJASIS VILNIUS""";"Vilniaus m. sav.";561100;56.11.00;"Restoranų veikla";202601;1449.38;50;;0;16170.21
41055;110379432;"UŽDAROJI AKCINĖ BENDROVĖ ""NAUJASIS VILNIUS""";"Vilniaus m. sav.";561100;56.11.00;"Restoranų veikla";202602;;3;;0;
99999;110004884;"UAB ""VILLON""";"Vilniaus r. sav.";682000;68.20.00;"Nekilnojamojo turto nuoma";202601;;2;;0;
'''


def test_jar_keeps_only_vilnius_city_companies():
    companies = read_jar_vilnius(io.StringIO(JAR_SAMPLE))

    assert list(companies) == ["110379432"]
    company = companies["110379432"]
    assert company["name"] == 'Uždaroji akcinė bendrovė "Naujasis Vilnius"'
    assert company["address"] == "Vilnius, Gedimino pr. 1, LT-01103"
    assert company["registered_on"] == "1992-03-10"


def test_sodra_keeps_only_known_companies_and_parses_fields():
    rows = read_sodra(io.StringIO(SODRA_SAMPLE), {"110379432"})

    assert len(rows) == 2
    assert rows[0] == {
        "company_code": "110379432",
        "month": "2026-01-01",
        "insured": 50,
        "avg_wage": "1449.38",
        "contributions": "16170.21",
        "activity_code": "56.11.00",
        "activity_name": "Restoranų veikla",
    }
    assert rows[1]["avg_wage"] is None
    assert rows[1]["insured"] == 3


def test_latest_activity_uses_most_recent_month():
    monthly = [
        {"company_code": "1", "month": "2026-02-01", "activity_code": "56.11.00", "activity_name": "B"},
        {"company_code": "1", "month": "2026-01-01", "activity_code": "47.11.00", "activity_name": "A"},
    ]

    assert latest_activity(monthly) == {"1": ("56.11.00", "B")}