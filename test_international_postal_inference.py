#!/usr/bin/env python3
"""
Test: Inférence universelle code postal → ville (tous les pays supportés)
Démontre que le moteur peut désormais déduire la ville depuis le code postal
et le pays, à l'échelle internationale (pas juste Tunisie).
"""

from src.pipeline import run_pipeline


def test_case(msg, country_code, expected_country, expected_town, expected_postal, desc):
    """Helper pour tester un cas"""
    print(f"\n{'='*70}")
    print(f"📍 Test: {desc}")
    print(f"Message: {msg[:60]}...")
    
    result, _ = run_pipeline(msg, message_id="TEST_INT_POSTAL")
    
    ct = result.country_town
    print(f"\nRésultat:")
    print(f"  Country: {ct.country} (attendu: {expected_country})")
    print(f"  Town:    {ct.town} (attendu: {expected_town})")
    print(f"  Postal:  {ct.postal_code} (attendu: {expected_postal})")
    
    # Vérifications
    assert ct.country == expected_country, f"Country mismatch: {ct.country} != {expected_country}"
    assert ct.town == expected_town, f"Town mismatch: {ct.town} != {expected_town}"
    if expected_postal:
        assert ct.postal_code == expected_postal, f"Postal mismatch: {ct.postal_code} != {expected_postal}"
    
    # Vérifier que l'inférence a eu lieu
    has_inference_warning = any("geo_postal_inference_" in str(w) for w in result.meta.warnings)
    if expected_town and not msg.count(expected_town):  # Si la ville n'était pas explicite
        assert has_inference_warning, f"Pas de warning d'inférence trouvé. Warnings: {result.meta.warnings}"
        print(f"✅ Inférence détectée (geo_postal_inference_*)")
    
    print(f"✅ Test réussi!")
    return True


# Tests internationaux
def main():
    print("🌍 TESTS INFÉRENCE INTERNATIONALE CODE POSTAL → VILLE")
    print("="*70)
    
    # Test 1: TUNISIE - Format structuré avec code postal uniquement (pas de ville explicite)
    test_case(
        msg=""":50F:/TN5908003000716021093649
1/SOCIETE TEST
2/RUE DE PARIS
3/TN/1000""",
        country_code="TN",
        expected_country="TN",
        expected_town="TUNIS",
        expected_postal="1000",
        desc="Tunisie: code postal 1000 → inférer TUNIS"
    )
    
    # Test 2: TUNISIE - Autre ville
    test_case(
        msg=""":50F:/TN5908003000716021093649
1/COMPANY NAME
2/RUE PRINCIPALE
3/TN/8000""",
        country_code="TN",
        expected_country="TN",
        expected_town="NABEUL",
        expected_postal="8000",
        desc="Tunisie: code postal 8000 → inférer NABEUL"
    )
    
    # Test 3: FRANCE - Paris avec code postal
    test_case(
        msg=""":50F:/FR7630004000380001003225185
1/ACME CORPORATION
2/123 RUE DE RIVOLI
3/FR/75001""",
        country_code="FR",
        expected_country="FR",
        expected_town="PARIS",
        expected_postal="75001",
        desc="France: code postal 75001 → inférer PARIS"
    )
    
    # Test 4: ROYAUME-UNI - Londres  
    test_case(
        msg=""":50F:/GB89370400440532013000
1/ACME CORPORATION LTD
2/45 CANARY WHARF
3/GB/E14 5AB""",
        country_code="GB",
        expected_country="GB",
        expected_town="LONDON",
        expected_postal="E14 5AB",
        desc="UK: code postal E14 5AB → inférer LONDON"
    )
    
    # Test 5: ALLEMAGNE - Berlin
    test_case(
        msg=""":50F:/DE89370400440532013000
1/BERLIN COMPANY
2/KURFURSTENDAMM 100
3/DE/10115""",
        country_code="DE",
        expected_country="DE",
        expected_town="BERLIN",
        expected_postal="10115",
        desc="Allemagne: code postal 10115 → inférer BERLIN"
    )
    
    # Test 6: USA - New York
    test_case(
        msg=""":50F:/US00000123456789012345
1/NEW YORK BANK
2/350 FIFTH AVENUE
3/US/10001""",
        country_code="US",
        expected_country="US",
        expected_town="NEW YORK",
        expected_postal="10001",
        desc="USA: code postal 10001 → inférer NEW YORK"
    )
    
    # Test 7: CHINE - Beijing (format libre)
    test_case(
        msg=""":50K:/CN12345678901234567890
北京公司
北京市朝阳区建国门外大街1号
邮编:100000""",
        country_code="CN",
        expected_country="CN",
        expected_town="BEIJING",
        expected_postal="100000",
        desc="Chine: code postal 100000 → inférer BEIJING"
    )
    
    # Test 8: JAPON - Tokyo (format libre)
    test_case(
        msg=""":50K:/JP12345678901234567890
東京会社
東京都千代田区丸の内1-1-1
〒100-0001""",
        country_code="JP",
        expected_country="JP",
        expected_town="TOKYO",
        expected_postal="100-0001",
        desc="Japon: code postal 100-0001 → inférer TOKYO"
    )
    
    print("\n" + "="*70)
    print("🎉 TOUS LES TESTS RÉUSSIS!")
    print("✅ L'inférence internationale est standardisée pour tous les pays")
    print("="*70)


if __name__ == "__main__":
    main()
