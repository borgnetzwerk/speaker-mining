# Series Examples

## ZDF Archiv
season_id,season_label,start_time,end_time,episode_count
se_66b45c504b04,"Markus Lanz, Staffel 1",03.06.2008,04.09.2008,29
se_2dcbfca1700e,"Markus Lanz, Staffel 2",16.06.2009,16.12.2009,53
se_aefb2a93a519,"Markus Lanz, Staffel 3",13.01.2010,15.12.2010,96

## Wikidata
Mainly, series are listed here:
`data/20_candidate_generation/wikidata/projections/instances_core_series.json`

Note that some may also listed as broadcasting_prgrams, for example every "P31" of "Q3464665" (since "television series season" is also a broadcasting program)
`data/20_candidate_generation/wikidata/projections/instances_core_broadcasting_programs.json`

We can always search in data\20_candidate_generation\wikidata\projections\triples.csv for any subject that has ",P31,Q3464665", meaning `predicate` `P31` and `object` `Q3464665`.

### From data/20_candidate_generation/wikidata/projections/instances_core_broadcasting_programs.json
  "Q130559283": {
    "_fetched_literal_languages": [
      "de",
      "en"
    ],
    "type": "item",
    "id": "Q130559283",
    "labels": {
      "en": {
        "language": "en",
        "value": "Markus Lanz, season 17"
      },
      "de": {
        "language": "de",
        "value": "Markus Lanz, Staffel 17"
      },
      "mul": {
        "value": "Markus Lanz, season 17",
        "language": "en",
        "for-language": "mul"
      }
    },
    "descriptions": {
      "en": {
        "language": "en",
        "value": "season of German television talk show (2024/2025)"
      },
      "de": {
        "language": "de",
        "value": "Staffel der deutschen Fernsehtalkshow Markus Lanz (2024/2025)"
      },
      "mul": {
        "value": "season of German television talk show (2024/2025)",
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
            "hash": "595ab1e400b931867076ef6acd376bbb37f76d11",
            "datavalue": {
              "value": {
                "entity-type": "item",
                "numeric-id": 3464665,
                "id": "Q3464665"
              },
              "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
          },
          "type": "statement",
          "id": "Q130559283$fd3421c7-4c55-a5ec-bcf0-a447f8de163d",
          "rank": "normal"
        }
      ],
      "P179": [
        {
          "mainsnak": {
            "snaktype": "value",
            "property": "P179",
            "hash": "a6bfffaea5630d572b1de0d02a6c6310077c8c5c",
            "datavalue": {
              "value": {
                "entity-type": "item",
                "numeric-id": 1499182,
                "id": "Q1499182"
              },
              "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
          },
          "type": "statement",
          "qualifiers": {
            "P1545": [
              {
                "snaktype": "value",
                "property": "P1545",
                "hash": "1486eb16323ccfa872de81f5a62795658dfa8c93",
                "datavalue": {
                  "value": "17",
                  "type": "string"
                },
                "datatype": "string"
              }
            ],
            "P155": [
              {
                "snaktype": "value",
                "property": "P155",
                "hash": "b9b1c7add62f3b5c33f9496174183e00fcf82708",
                "datavalue": {
                  "value": {
                    "entity-type": "item",
                    "numeric-id": 132855776,
                    "id": "Q132855776"
                  },
                  "type": "wikibase-entityid"
                },
                "datatype": "wikibase-item"
              }
            ],
            "P156": [
              {
                "snaktype": "value",
                "property": "P156",
                "hash": "f06530cb63f72ac08b662e916ecea77b0a2a9495",
                "datavalue": {
                  "value": {
                    "entity-type": "item",
                    "numeric-id": 135987467,
                    "id": "Q135987467"
                  },
                  "type": "wikibase-entityid"
                },
                "datatype": "wikibase-item"
              }
            ]
          },
          "qualifiers-order": [
            "P1545",
            "P155",
            "P156"
          ],
          "id": "Q130559283$01830d02-43d4-dddf-5703-3153684a024e",
          "rank": "normal"
        }
      ],
      "P580": [
        {
          "mainsnak": {
            "snaktype": "value",
            "property": "P580",
            "hash": "772badcefa57207fc457dd44e6ec45465b9a0f98",
            "datavalue": {
              "value": {
                "time": "+2024-08-29T00:00:00Z",
                "timezone": 0,
                "before": 0,
                "after": 0,
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727"
              },
              "type": "time"
            },
            "datatype": "time"
          },
          "type": "statement",
          "id": "Q130559283$e55a7243-4c91-1136-9f35-6f99fd75cf10",
          "rank": "normal"
        }
      ],
      "P364": [
        {
          "mainsnak": {
            "snaktype": "value",
            "property": "P364",
            "hash": "42ea0fa04968ba469913886ef42bb109936ce230",
            "datavalue": {
              "value": {
                "entity-type": "item",
                "numeric-id": 188,
                "id": "Q188"
              },
              "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
          },
          "type": "statement",
          "id": "Q130559283$84398605-48b0-3eb9-2ce8-1f8e0c121a23",
          "rank": "normal"
        }
      ],
      "P449": [
        {
          "mainsnak": {
            "snaktype": "value",
            "property": "P449",
            "hash": "53a5f090c03e98ff9074d966581f9857b48cd500",
            "datavalue": {
              "value": {
                "entity-type": "item",
                "numeric-id": 48989,
                "id": "Q48989"
              },
              "type": "wikibase-entityid"
            },
            "datatype": "wikibase-item"
          },
          "type": "statement",
          "id": "Q130559283$7edeccfd-4e7a-52e4-fdd2-f6061c00a12e",
          "rank": "normal"
        }
      ],
      ...

## Fernsehserien.de
n.a.