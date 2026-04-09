# Episode Examples

## ZDF Archiv
### From data/10_mention_detection/episodes.csv
episode_id,sendungstitel,publikation_id,publikationsdatum,dauer,archivnummer,prod_nr_beitrag,zeit_tc_start,zeit_tc_end,season,staffel,folge,folgennr,infos
ep_a371a3777018,Markus Lanz 03.06.2008,pb_e81cb7939cdb,03.06.2008,69'54,4010956801,00529/00175,,,"Markus Lanz, Staffel 1",,,,"00:01:48 - 01:11:14 069'26 Interview Markus LANZ mit Verona POOTH (Werbeikone) über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"") und ihr Ehemann Peter WAHLER, Udo BAUCH (Überlebender vom ICE-Unglück in Eschede) und seine Ehefrau Monika BAUCH und Georg PIEPER (Traumaexperte) (O-Ton)."
ep_36337a9dfb46,Markus Lanz 04.06.2008,pb_0b8fd4b20dc9,04.06.2008,59'51,4010941101,00529/00176,,,"Markus Lanz, Staffel 1",,,,"23:17:10 - 00:16:35 059'25 Interview Markus LANZ mit den Studiogästen Horst LICHTER (Fernsehkoch), Margret LICHTER (Mutter von Horst Lichter), Michael BAUER (Hoteltester) und Steffen MÖLLER (Moderator, Autor und Schauspieler) (O-Ton)."
ep_145cdbbd9501,Markus Lanz 05.06.2008,pb_76cf822d1aa2,05.06.2008,60'12,4010950101,00529/00177,,,"Markus Lanz, Staffel 1",,,,"23:16:15 - 00:15:52 059'37 Interview Markus LANZ mit den Studiogästen Ralf MÖLLER (Schauspieler), Rüdiger NEHBERG (Abenteurer) und Anka KRÄMER DE HUERTA (Ethnologin) und Michael SCHRECKENBERG (Stauexperte) (O-Ton); SCHRECKENBERG erklärt im Studio anhand von Modellautos das Nagel-Schreckenberg-Modell; LANZ zieht Tarnanzug von Soldaten an."

### From data/10_mention_detection/publications.csv
publikation_id,episode_id,publication_index,date,time,duration,program,prod_nr_sendung,prod_nr_secondary,is_primary,raw_line
pb_e81cb7939cdb,ep_a371a3777018,1,03.06.2008,22:44:42,69'54,ZDF,00529/00175,,1,03.06.2008 22:44:42 69'54 00529/00175 ZDF
pb_12f66ecd45ea,ep_a371a3777018,2,04.06.2008,02:35:35,69'52,ZDF,00529/50117,,0,04.06.2008 02:35:35 69'52 00529/50117 ZDF
pb_d9e6d9bab453,ep_a371a3777018,3,07.06.2008,17:03:31,66'58,ZDFdokukanal,00742/08091,,0,07.06.2008 17:03:31 66'58 00742/08091 ZDFdokukanal

## Wikidata
### From data/20_candidate_generation/wikidata/projections/instances_core_episodes.csv
Q130625348,Q21191270,,Deutschland in der Krise – was kann Olaf Scholz noch erreichen?,Deutschland in der Krise – was kann Olaf Scholz noch erreichen?,Sendung der Fernsehtalkshow Maybrit Illner von 2024 (S26E7),2024 episode of television talk show Maybrit Illner (S26E7),,,Q21191270|Q1983062,True,2026-04-02T21:14:21Z,2026-04-07T15:22:24Z
Q130637713,Q21191270,,Markus Lanz (23. Oktober 2024),"Markus Lanz (October 23rd, 2024)",Sendung der Fernsehtalkshow Markus Lanz von 2024 (S17E26),2024 episode of television talk show Markus Lanz (S17E26),,,Q21191270|Q1983062,True,2026-04-02T21:01:47Z,2026-04-07T15:22:24Z
Q130638552,Q21191270,,Markus Lanz (24. Oktober 2024),"Markus Lanz (October 24th, 2024)",Sendung der Fernsehtalkshow Markus Lanz von 2024 (S17E27),2024 episode of television talk show Markus Lanz (S17E27),,,Q21191270|Q1983062,True,2026-04-02T21:01:48Z,2026-04-07T15:22:25Z
Q130710696,Q21191270,,Deutschland in der Autokrise: Fährt eine Industrie gegen die Wand?,Deutschland in der Autokrise: Fährt eine Industrie gegen die Wand?,Sendung der Fernsehtalkshow Hart aber fair von 2024 (S25E10),2024 episode of television talk show Hart aber fair (S25E10),,,Q21191270|Q1983062,True,2026-04-02T21:05:56Z,2026-04-07T15:22:25Z

### From data/20_candidate_generation/wikidata/projections/entities.json
"Q130638552": {
    "id": "Q130638552",
    "labels": {
    "en": {
        "language": "en",
        "value": "Markus Lanz (October 24th, 2024)"
    },
    "de": {
        "language": "de",
        "value": "Markus Lanz (24. Oktober 2024)"
    },
    "mul": {
        "value": "Markus Lanz (October 24th, 2024)",
        "language": "en",
        "for-language": "mul"
    }
    },
    "descriptions": {
    "en": {
        "language": "en",
        "value": "2024 episode of television talk show Markus Lanz (S17E27)"
    },
    "de": {
        "language": "de",
        "value": "Sendung der Fernsehtalkshow Markus Lanz von 2024 (S17E27)"
    },
    "mul": {
        "value": "2024 episode of television talk show Markus Lanz (S17E27)",
        "language": "en",
        "for-language": "mul"
    }
    },
    "aliases": {},
    "claims": {
    "P31": [
        {
        "mainsnak": {
            "snaktype": "value",
            "property": "P31",
            "hash": "2d3761f68cf1248dc8fbf0b5eaa1f7fff03df987",
            "datavalue": {
            "value": {
                "entity-type": "item",
                "numeric-id": 21191270,
                "id": "Q21191270"
            },
            "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
        },
        "type": "statement",
        "id": "Q130638552$A3F3726A-DEAB-46FB-8887-6F7C654B5391",
        "rank": "normal"
        }
    ],
    "P279": []
    },
    "discovered_at_utc": "2026-04-02T21:01:48Z",
    "discovered_at_utc_history": [
    "2026-04-02T21:01:48Z",
    "2026-04-07T15:22:25Z",
    "2026-04-07T16:01:38Z"
    ],
    "expanded_at_utc": "2026-04-07T15:22:25Z",
    "type": "item",
    "_fetched_literal_languages": [
    "de",
    "en"
    ],
    "expanded_at_utc_history": [
    "2026-04-07T15:22:25Z"
    ]
},

## Fernsehserien.de
### data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv
fernsehserien_de_id,program_name,episode_url,episode_title,duration_minutes,description_text,description_source,premiere_date,premiere_broadcaster,normalized_at_utc,normalizer_rule,source_discovered_sequence,source_event_sequence
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,Folge 1,,Episoden,,2008-06-03,ZDF,2026-04-08T11:42:57Z,episode_description_norm_v1,322,678
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/10-folge-10-514627,Folge 10,,Episoden,,2008-07-03,ZDF,2026-04-08T11:42:57Z,episode_description_norm_v1,333,679
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1026-folge-1026-1110561,Folge 1026,,Episoden,,2017-08-22,ZDF,2026-04-08T11:42:57Z,episode_description_norm_v1,343,680

### data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_normalized.csv
fernsehserien_de_id,program_name,episode_url,broadcast_date,broadcast_start_time,broadcast_end_date,broadcast_end_time,broadcast_timezone_offset,broadcast_broadcaster,broadcast_broadcaster_key,broadcast_is_premiere,broadcast_spans_next_day,broadcast_order,normalized_at_utc,normalizer_rule,source_discovered_sequence,source_event_sequence
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,2008-06-05,02:35,,03:35,+02:00,ZDF,,False,False,0,2026-04-08T11:43:01Z,episode_broadcast_norm_v1,330,913
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,2008-06-03,22:45,,23:45,+02:00,ZDF,,True,False,1,2026-04-08T11:43:01Z,episode_broadcast_norm_v1,331,914
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/10-folge-10-514627,2008-07-04,00:00,,01:00,+02:00,ZDF,,False,False,0,2026-04-08T11:43:01Z,episode_broadcast_norm_v1,340,915
