    def _apply_slm_result(self, party: CanonicalParty, 
                          slm_result: Dict[str, Any]) -> CanonicalParty:
        """
        Fusionne le résultat SLM avec le party existant.
        Stratégie conservative: ne remplace que si meilleur ou manquant.
        """
        updated = False
        
        # 1. Nom (toujours prendre le SLM si différent et plus complet)
        if slm_result.get('name'):
            current_name = ' '.join(party.name) if party.name else ''
            slm_name = slm_result['name']
            current_country = party.country_town.country if party.country_town else None
            
            # Prendre prioritairement le nom du SLM si c'est un format 50K bruités
            if party.field_type == "50K":
                party.name = [slm_name]
                updated = True
                logger.debug(f"[E3] Nom forcé en 50K : {slm_name}")
            elif _name_just_appends_same_country(current_name, slm_name, current_country):
                pass
            elif current_name == "UNKNOWN" or len(slm_name) >= len(current_name) - 3 or not current_name:
                party.name = [slm_name]
                updated = True
                logger.debug(f"[E3] Nom mis à jour: {slm_name}")
        
        # 2. Adresse (ajouter si manquante)
        sanitized_addresses = [line for line in slm_result.get('address_lines', []) 
                            if not _contains_account_text(line, party.account)]
                            
        # ✅ REDONDANCE : Nettoyer la ville, le code postal et le pays des lignes d'adresse
        clean_address_lines = []
        for line in sanitized_addresses:
            c_line = line
            if slm_result.get('town') and str(slm_result['town']).upper() in c_line.upper():
                c_line = re.compile(re.escape(str(slm_result['town'])), re.IGNORECASE).sub('', c_line)
            if slm_result.get('postal') and str(slm_result['postal']) in c_line:
                c_line = c_line.replace(str(slm_result['postal']), '')
            if slm_result.get('country') and str(slm_result['country']).upper() in c_line.upper():
                c_line = re.compile(re.escape(str(slm_result['country'])), re.IGNORECASE).sub('', c_line)
            # Retirer aussi les mots comme "TUNISIE" si present
            c_line = re.compile(r'\b(?:TUNISIE|TUNISIA|TUN|TU)\b', re.IGNORECASE).sub('', c_line)
            
            c_line = c_line.strip(',.- ')
            # Retirer les espaces multiples cachés (regex)
            c_line = re.sub(r'\s{2,}', ' ', c_line).strip()
            c_line = _restore_unit_identifier(c_line, party.raw or party.account)
            
            if len(c_line) > 1:
                clean_address_lines.append(c_line)

        party.address_lines = clean_address_lines
        updated = True
        logger.debug(f"[E3] Adresse mise à jour et nettoyée: {clean_address_lines}")
        
        # 3. Pays (priorité si manquant ou différent de l'IBAN)
        if slm_result.get('country'):
            if not party.country_town or not party.country_town.country:
                party.country_town = CountryTown(
                    country=slm_result['country'],
                    town=party.country_town.town if party.country_town else None,
                    postal_code=party.country_town.postal_code if party.country_town else None
                )
                updated = True
                logger.debug(f"[E3] Pays ajouté: {slm_result['country']}")
            elif party.country_town.country != slm_result['country']:
                party.country_town.country = slm_result['country']
                updated = True
                logger.debug(f"[E3] Pays mis à jour: {slm_result['country']}")
        
        # 4. Ville (priorité si manquante ou contient adresse)
        if slm_result.get('town'):
            current_town = party.country_town.town if party.country_town else ''
            slm_town = slm_result['town']
            
            # Prendre le SLM si la ville actuelle contient des mots d'adresse ou est fausse
            address_keywords = ['PO BOX', 'RUE', 'STREET', 'AVENUE', 'DEPT', 'DEPARTMENT']
            has_address_words = bool(current_town) and any(kw in current_town for kw in address_keywords)
            
            # Priorité absolue au SLM pour corriger les villes
            if not current_town or current_town == "UNKNOWN" or has_address_words or len(slm_town) >= 3:
                if not party.country_town:
                    party.country_town = CountryTown(country=None, town=slm_town, postal_code=None)
                else:
                    party.country_town.town = slm_town
                updated = True
                logger.debug(f"[E3] Ville mise à jour par SLM: {slm_town}")
        
        # 5. Code postal
        if slm_result.get('postal_code'):
            if party.country_town:
                party.country_town.postal_code = slm_result['postal_code']
                updated = True
        
        # Mise à jour des métadonnées
        _meta_set(party.meta, 'llm_signals', ['slm_applied'])
        _meta_set(party.meta, 'fallback_used', True)

        if updated:
            # Augmenter légèrement la confiance si SLM a amélioré
            current_confidence = _meta_get(party.meta, 'parse_confidence', 0.5)
