# Person Examples

## ZDF Archiv
mention_id,episode_id,name,beschreibung,source_text,source_context,parsing_rule,confidence,confidence_note
pm_13aa6f5ec26b,ep_a371a3777018,Franjo Pooth,,"über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"")","Verona POOTH (Werbeikone) über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"") und ihr Ehemann Peter WAHLER, Udo BAUCH (Überlebender vom ICE-Unglück in Eschede) und seine Ehefrau Monika BAUCH und Georg PIEPER (Traumaexperte)",name_without_local_parenthetical,0.45,name appears in multi-name chain; description withheld to avoid misattribution
pm_29eaeb7e7965,ep_a371a3777018,Georg PIEPER,Traumaexperte,und seine Ehefrau Monika BAUCH und Georg PIEPER (Traumaexperte),"Verona POOTH (Werbeikone) über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"") und ihr Ehemann Peter WAHLER, Udo BAUCH (Überlebender vom ICE-Unglück in Eschede) und seine Ehefrau Monika BAUCH und Georg PIEPER (Traumaexperte)",last_name_parenthetical,0.82,description assigned to nearest name before parenthetical
pm_68f5f9919a8e,ep_a371a3777018,Jelena WAHLER,"Gründerin Elitekindergarten ""Little Giants""","über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"")","Verona POOTH (Werbeikone) über die Insolvenzaffäre von ihrem Ehemann Franjo Pooth; weitere Studiogäste sind Jelena WAHLER (Gründerin Elitekindergarten ""Little Giants"") und ihr Ehemann Peter WAHLER, Udo BAUCH (Überlebender vom ICE-Unglück in Eschede) und seine Ehefrau Monika BAUCH und Georg PIEPER (Traumaexperte)",last_name_parenthetical,0.82,description 

## Wikidata
### From data/20_candidate_generation/wikidata/projections/instances_core_persons.csv
id,class_id,class_filename,label_de,label_en,description_de,description_en,alias_de,alias_en,path_to_core_class,subclass_of_core_class,discovered_at_utc,expanded_at_utc
Q100157363,Q5,,David Gardiner Tyler Jr.,David Gardiner Tyler Jr.,grandson of U.S. president John Tyler,grandson of U.S. president John Tyler,,"David Gardiner Tyler, Jr.",Q5|Q215627,True,2026-04-07T15:20:48Z,
Q100175,Q5,,Lilli Schweiger,Lilli Schweiger,deutsche Schauspielerin,German actress,Lilli Camille Schweiger,Lilli Camille Schweiger,Q5|Q215627,True,2026-04-07T13:03:53Z,
Q100252,Q5,,Johann Nepomuk von Ringseis,Johann Nepomuk von Ringseis,deutscher Arzt,German physician (1785-1880),Johann Nepomuk Ringseis|Johann Ringeis,,Q5|Q215627,True,2026-04-07T13:03:53Z,

### From data/20_candidate_generation/wikidata/projections/entities.json
"Q100175": {
    "id": "Q100175",
    "labels": {
    "de": {
        "language": "de",
        "value": "Lilli Schweiger"
    },
    "en": {
        "language": "en",
        "value": "Lilli Schweiger"
    },
    "mul": {
        "language": "mul",
        "value": "Lilli Schweiger"
    }
    },
    "descriptions": {
    "de": {
        "language": "de",
        "value": "deutsche Schauspielerin"
    },
    "en": {
        "language": "en",
        "value": "German actress"
    },
    "mul": {
        "value": "German actress",
        "language": "en",
        "for-language": "mul"
    }
    },
    "aliases": {
    "en": [
        {
        "language": "en",
        "value": "Lilli Camille Schweiger"
        }
    ],
    "de": [
        {
        "language": "de",
        "value": "Lilli Camille Schweiger"
        }
    ]
    },
    "claims": {
    "P31": [
        {
        "mainsnak": {
            "snaktype": "value",
            "property": "P31",
            "hash": "ad7d38a03cdd40cdc373de0dc4e7b7fcbccb31d9",
            "datavalue": {
            "value": {
                "entity-type": "item",
                "numeric-id": 5,
                "id": "Q5"
            },
            "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
        },
        "type": "statement",
        "id": "Q100175$7B7E4F79-FEB8-40E9-A464-1C9031094880",
        "rank": "normal",
        "references": [
            {
            "hash": "fa278ebfc458360e5aed63d5058cca83c46134f1",
            "snaks": {
                "P143": [
                {
                    "snaktype": "value",
                    "property": "P143",
                    "hash": "e4f6d9441d0600513c4533c672b5ab472dc73694",
                    "datavalue": {
                    "value": {
                        "entity-type": "item",
                        "numeric-id": 328,
                        "id": "Q328"
                    },
                    "type": "wikibase-entityid"
                    },
                    "datatype": "wikibase-item"
                }
                ]
            },
            "snaks-order": [
                "P143"
            ]
            }
        ]
        }
    ],
    "P279": []
    },
    "discovered_at_utc": "2026-04-07T13:03:53Z",
    "discovered_at_utc_history": [
    "2026-04-07T13:03:53Z"
    ],
    "expanded_at_utc": null
},

## Fernsehserien.de
fernsehserien_de_id,program_name,episode_url,guest_name,guest_role,guest_description,guest_url,guest_image_url,guest_order,normalized_at_utc,normalizer_rule,source_discovered_sequence,source_event_sequence
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,Verona Pooth,Gast,,https://www.fernsehserien.de/verona-pooth/filmografie,https://bilder.fernsehserien.de/gfx/person_1000/v/verona-pooth-5788-1751957525.jpg,0,2026-04-08T11:42:58Z,episode_guest_norm_v1,323,726
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,Jelena Wahler,Gast,Gründerin des Kindergartenmodell s „Little Giants“,https://www.fernsehserien.de/jelena-wahler/filmografie,https://bilder.fernsehserien.de/fernsehserien.de/fs-2021/img/Person.svg,1,2026-04-08T11:42:58Z,episode_guest_norm_v1,324,727
markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614,Susanne Meister,Gast,ihr Kind besucht einen „Elite-Kindergarten“,https://www.fernsehserien.de/susanne-meister/filmografie,https://bilder.fernsehserien.de/fernsehserien.de/fs-2021/img/Person.svg,2,2026-04-08T11:42:58Z,episode_guest_norm_v1,325,728
