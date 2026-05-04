## Fernsehserien ID issue propagation
Overview:
1. Episodes are extracted from fernsehserien.de
2. Later, data from different sources (ZDF, Wikidata)
   1. Here, when Persons are added, there is a bug that assigns these persons the wrong ID
3. Later, when persons are mapped to episodes, this wrong ID may cause issues.

### How it should be
This from `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv` below is authorative as to what we retrieve from fernsehserien.de:

```
fernsehserien_de_id,program_name,episode_url,episode_title_raw,duration_raw,description_raw_text,description_source_raw,premiere_date_raw,premiere_broadcaster_raw,raw_extra_json,parsed_at_utc,parser_rule,confidence,source_event_sequence
couchwissen,couchwissen,https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580,Alles steht Kopf – Filmgespräch,,Episoden,,Mi. 02.10.2024,YouTube,"{""guests_count"": 0, ""broadcasts_count"": 0}",2026-04-09T09:25:21Z,leaf_v1_raw_structured,0.78,105789
```

As well as this from `data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv`:
```
fernsehserien_de_id,program_name,episode_url,guest_name,guest_role,guest_description,guest_url,guest_image_url,guest_order,normalized_at_utc,normalizer_rule,source_discovered_sequence,source_event_sequence
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1992-sendung-vom-02-10-2024-1747178,Phoebe Gaa,Gast,ZDF-Korrespondentin,https://www.fernsehserien.de/phoebe-gaa/filmografie,https://bilder.fernsehserien.de/fernsehserien.de/fs-2021/img/Person.svg,3,2026-04-08T13:58:08Z,episode_guest_norm_v1,4161,12194
```

As we see: According to fernsehserien.de, there is no connection between Phoebe Gaa (Fernsehserien ID: phoebe-gaa) and Alles Steht Kopf - Filmgespräch (Fernsehserien ID: 3x01-alles-steht-kopf-filmgespraech-1762580).

### The downstream issue
During aligning, we create the issue: `data/31_entity_disambiguation/aligned/aligned_persons.csv`:

```
alignment_unit_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,open_refine_name,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes,label_wikidata,label_fernsehserien_de,label_zdf,description_wikidata,description_fernsehserien_de,description_zdf,alias_wikidata,alias_fernsehserien_de,alias_zdf,episode_id_zdf,mention_id_zdf,name_zdf,mention_category_zdf,beschreibung_zdf,source_text_zdf,source_context_zdf,parsing_rule_zdf,confidence_zdf,confidence_note_zdf,fernsehserien_de_id_fernsehserien_de,program_name_fernsehserien_de,episode_url_fernsehserien_de,guest_name_fernsehserien_de,guest_role_fernsehserien_de,guest_description_fernsehserien_de,guest_url_fernsehserien_de,guest_image_url_fernsehserien_de,guest_order_fernsehserien_de,normalized_at_utc_fernsehserien_de,normalizer_rule_fernsehserien_de,source_discovered_sequence_fernsehserien_de,source_event_sequence_fernsehserien_de,entity_id_wikidata,entity_type_wikidata
pm_77b63df9a94a,Q87645128,https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580,pm_77b63df9a94a,Phoebe GAA,Phoebe GAA,person,0.83,high,episode_context_name_exact,unique label-equal wikidata person,,,false,,,Phoebe Gaa,,Phoebe GAA,deutsche Fernsehmoderatorin,,"ZDF-Korrespondentin, Zuschaltung über Videotelefonie",,,,ep_c3bc46df8b7e,pm_77b63df9a94a,Phoebe GAA,guest,"ZDF-Korrespondentin, Zuschaltung über Videotelefonie","Phoebe GAA (ZDF-Korrespondentin, Zuschaltung über Videotelefonie)","den Studiogästen Bente SCHELLER (Politikwissenschaftlerin, Heinrich-Böll-Stiftung), Carlo MASALA (Militärexperte, Universität der Bundeswehr München), Phoebe GAA (ZDF-Korrespondentin, Zuschaltung über Videotelefonie), Katrin EIGENDORF (ZDF-Korrespondentin, Zuschaltung über Videotelefonie) und Christoph EHRHARDT (Journalist, ""FAZ"", Zuschaltung über Videotelefonie) über die Schwerpunktthemen: - die Lage im Libanon nach dem Beginn der Bodenoffensive Israels - die Situation nach dem Angriff des Irans auf Israel und die möglichen Handlungen der israelischen Regierung und ihrer Verbündeten - die Situation im Iran nach dem Angriff des Irans auf Israel - das iranische Atomprogramm",single_parenthetical,0.95,single name directly tied to parenthetical description,,,,,,,,,,,,,,Q87645128,item
```

The issue is much worse than we thought:
Not only is the fernsehserien_de_id not of the person, but of the episode:
It is an ID of an episode that seems to be unrelated to the person!

### Validation
Every occurrence in analysis is wrong:

```
canonical_entity_id,canonical_label,https://www.fernsehserien.de/couchwissen/folgen/1x03-wie-realistisch-ist-apollo-13-1658096,https://www.fernsehserien.de/couchwissen/folgen/1x05-wie-realistisch-ist-arrival-1685761,https://www.fernsehserien.de/couchwissen/folgen/2x03-portal-2-wissenschaftlich-gecheckt-1734433,https://www.fernsehserien.de/couchwissen/folgen/2x06-cities-skylines-bau-deine-eigene-stadt-1738907,https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580,https://www.fernsehserien.de/couchwissen/folgen/3x02-detroit-become-human-wissenschaftlich-gezockt-1762579
ce_ae1202b97ba3,Elmar THEVEßEN,,,,1,,
ce_6812b9d00caa,Robin ALEXANDER,,,,1,,
ce_3cc93caac2ae,Kerstin MÜNSTERMANN,,,,,,1
ce_cfaaa6a17474,Jens SPAHN,,1,,,,
ce_b194001d7145,Kristin HELBERG,,,,,,1
ce_d560615ea2da,Katrin EIGENDORF,,,,,1,
ce_4fa4560220cc,Carlo MASALA,,,,,1,
ce_0aaf988db67d,Rüdiger VON FRITSCH,,,1,,,
ce_b7cde3efa0cf,Saskia ESKEN,,,1,,,
ce_f47ef66b73d4,Linda TEUTEBERG,,,,1,,1
ce_690395ccc5e0,Petra PINZLER,,1,,,,
ce_0be418807e52,Bettina STARK-WATZINGER,1,,,,,
ce_1d0d3890a3ca,Christoph EHRHARDT,,,,,1,
ce_5d91aa954605,Philipp PEYMAN ENGEL,,1,,,,1
ce_9435b5372f8c,Jürgen SCHMIDHUBER,1,,,,,
ce_42c3d743e382,Sonja ALVAREZ,1,,,,,
ce_e7fe9c31f0cd,Britta HILPERT,,,1,,,
ce_00e0cd6e4bbc,Phoebe GAA,,,,,1,
ce_579080ef19b5,Bente SCHELLER,,,,,1,
ce_85b15e85b8a7,Kubilay DERTLI,,1,,,,
ce_c1b07c79082d,Simon SCHNETZER,,,1,,,
```

None of these people were ever guest at couchwissen.

### The source: wrong episode merging
ep_c3bc46df8b7e was a wrongful merge between https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580 and Markus Lanz 02.10.2024.

`data/31_entity_disambiguation/aligned/aligned_episodes.csv`

```
alignment_unit_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,open_refine_name,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes,label_wikidata,label_fernsehserien_de,label_zdf,description_wikidata,description_fernsehserien_de,description_zdf,alias_wikidata,alias_fernsehserien_de,alias_zdf,publikationsdatum_zdf,dauer_zdf,season_zdf,fernsehserien_de_id_fernsehserien_de,program_name_fernsehserien_de,episode_url_fernsehserien_de,episode_title_fernsehserien_de,duration_minutes_fernsehserien_de,description_text_fernsehserien_de,description_source_fernsehserien_de,premiere_date_fernsehserien_de,premiere_broadcaster_fernsehserien_de,normalized_at_utc_fernsehserien_de,normalizer_rule_fernsehserien_de,source_discovered_sequence_fernsehserien_de,source_event_sequence_fernsehserien_de,premiere_date_date_fernsehserien_de,guest_1_name_fernsehserien_de,guest_1_role_fernsehserien_de,broadcast_1_date_fernsehserien_de,broadcast_1_start_time_fernsehserien_de,broadcast_1_end_date_fernsehserien_de,broadcast_1_end_time_fernsehserien_de,broadcast_1_broadcaster_fernsehserien_de,broadcast_1_is_premiere_fernsehserien_de
ep_c3bc46df8b7e,,https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580,,Markus Lanz 02.10.2024,,episode,0.92,high,date_backbone_plus_title_signals,date-aligned fs episode,,,false,,,,Alles steht Kopf – Filmgespräch,Markus Lanz 02.10.2024,,Episoden,"00:00:43 - 00:45:55 045'12 O-Ton Interview Markus LANZ mit den Studiogästen Bente SCHELLER (Politikwissenschaftlerin, Heinrich-Böll-Stiftung), Carlo MASALA (Militärexperte, Universität der Bundeswehr München), Phoebe GAA (ZDF-Korrespondentin, Zuschaltung über Videotelefonie), Katrin EIGENDORF (ZDF-Korrespondentin, Zuschaltung über Videotelefonie) und Christoph EHRHARDT (Journalist, ""FAZ"", Zuschaltung über Videotelefonie) über die Schwerpunktthemen: - die Lage im Libanon nach dem Beginn der Bodenoffensive Israels - die Situation nach dem Angriff des Irans auf Israel und die möglichen Handlungen der israelischen Regierung und ihrer Verbündeten - die Situation im Iran nach dem Angriff des Irans auf Israel - das iranische Atomprogramm.",,,,02.10.2024,45'17,"Markus Lanz, Staffel 17",couchwissen,couchwissen,https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580,Alles steht Kopf – Filmgespräch,,Episoden,,2024-10-02,YouTube,2026-04-09T09:55:54Z,episode_description_norm_v1,105789,118439,2024-10-02 00:00:00,,,,,,,,
```



### Conclusion
We cannot trust any assigned fernsehserien_de IDS past Phase 2.
If we want to retrieve them: we must 
a) for now, go back to the source
b) eventually fix the issue that introduced the issue


### Note
* We did note the fernsehserien.de issue before, but we did not know that the issue was so severe and caused this much damage. This must be fixed immediately.
* We also note that the Episodes in every analysis are always using the fernsehserien.de ID of that episode. Since we do have a alignment_unit_id for every episode, but not a fernsehserien_de_id for every episode, we should always use alignment_unit_id, or we risk loosing episodes.