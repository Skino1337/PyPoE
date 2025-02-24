"""
Wiki lua exporter

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/wiki/parsers/lua.py                           |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

This small script reads the data from quest rewards and exports it to a lua
table for use on the unofficial Path of Exile wiki located at:
http://pathofexile.gamepedia.com

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

# Python
import warnings
from collections import OrderedDict, defaultdict

# Self
from PyPoE.poe.constants import RARITY
from PyPoE.cli.core import console, Msg
from PyPoE.cli.exporter import config
from PyPoE.cli.exporter.wiki.handler import ExporterHandler, ExporterResult
from PyPoE.cli.exporter.wiki.parser import BaseParser

# =============================================================================
# Globals
# =============================================================================

__all__= ['QuestRewardReader', 'LuaHandler']

# =============================================================================
# Functions
# =============================================================================


def lua_format_value(key, value):
    if isinstance(value, int):
        f = '\t\t%s=%s,\n'
    else:
        f = '\t\t%s="%s",\n'
    return f % (key, value)


def lua_formatter(outdata, key_order=None):
    out = []
    out.append('local data = {\n')
    for data in outdata:
        out.append('\t{\n')
        for key, value in data.items():
            if isinstance(value, (int, float)):
                out.append('\t\t%s=%s,\n' % (key, value))
            elif isinstance(value, (tuple, set, list)):
                values = []
                for v in value:
                    k = '%s' if isinstance(v, int) else '"%s"'
                    values.append(k % v)

                    values.append
                out.append('\t\t%s={%s},\n' % (key, ', '.join(values)))
            else:
                out.append('\t\t%s="%s",\n' % (key, value.replace('"', '\\"')))
        out.append('\t},\n')
    out.append('\n}')
    out.append('\n')
    out.append('return data')

    return ''.join(out)

# =============================================================================
# Classes
# =============================================================================


class GenericLuaParser(BaseParser):
    def _copy_from_keys(self, row, keys, out_data, index=None):
        copyrow = OrderedDict()
        for k, copy_data in keys:

            value = row[k]
            if value is not None and value != "":
                if 'value' in copy_data:
                    value = copy_data['value'](value)
                copyrow[copy_data['key']] = value

        if index is not None:
            try:
                out_data[index].update(copyrow)
            except IndexError:
                out_data.append(copyrow)
        else:
            out_data.append(copyrow)


class LuaHandler(ExporterHandler):
    def __init__(self, sub_parser):
        self.parser = sub_parser.add_parser('lua', help='Lua Exporter')
        self.parser.set_defaults(func=lambda args: self.parser.print_help())
        lua_sub = self.parser.add_subparsers()

        parser = lua_sub.add_parser(
            'quest_rewards',
            help='Extract quest rewards into lua.'
        )
        self.add_default_parsers(
            parser=parser,
            cls=QuestRewardReader,
            func=QuestRewardReader.read_quest_rewards,
        )

        parser = lua_sub.add_parser(
            'vendor_rewards',
            help='Extract quest vendor rewards into lua.',
        )
        self.add_default_parsers(
            parser=parser,
            cls=QuestRewardReader,
            func=QuestRewardReader.read_vendor_rewards,
        )

        parser = lua_sub.add_parser(
            'bestiary',
            help='Extract bestiary information',
        )
        self.add_default_parsers(
            parser=parser,
            cls=BestiaryParser,
            func=BestiaryParser.main,
        )

        parser = lua_sub.add_parser(
            'delve',
            help='Extract delve information',
        )
        self.add_default_parsers(
            parser=parser,
            cls=DelveParser,
            func=DelveParser.main,
        )

        parser = lua_sub.add_parser(
            'synthesis',
            help='Extract synthesis information',
        )
        self.add_default_parsers(
            parser=parser,
            cls=SynthesisParser,
            func=SynthesisParser.main,
        )

        parser = lua_sub.add_parser(
            'monster',
            help='Extract monster information',
        )
        self.add_default_parsers(
            parser=parser,
            cls=MonsterParser,
            func=MonsterParser.main,
        )


class BestiaryParser(GenericLuaParser):
    _files = [
        # pretty much chain loads everything we need
        'BestiaryRecipes.dat',
        'ClientStrings.dat',
    ]

    _COPY_KEYS_BESTIARY = (
        ('Id', {
            'key': 'id',
        }),
        ('HintText', {
            'key': 'header',
        }),
        ('Description', {
            'key': 'subheader',
        }),
        ('Notes', {
            'key': 'notes',
        }),
    )

    _COPY_KEYS_BESTIARY_COMPONENTS = (
        ('Id', {
            'key': 'id',
        }),
        ('MinLevel', {
            'key': 'min_level',
        }),
        ('BestiaryFamiliesKey', {
            'key': 'family',
            'value': lambda x: x['Name'],
        }),
        ('BestiaryGroupsKey', {
            'key': 'beast_group',
            'value': lambda x: x['Name'],
        }),
        ('BestiaryGenusKey', {
            'key': 'genus',
            'value': lambda x: x['Name'],
        }),
        ('ModsKey', {
            'key': 'mod_id',
            'value': lambda x: x['Id'],
        }),
        ('BestiaryCapturableMonstersKey', {
            'key': 'monster',
            'value': lambda x: x['Name'],
        }),
    )

    def main(self, parsed_args):
        recipes = []
        components = []
        recipe_components_temp = defaultdict(lambda:defaultdict(int))

        for row in self.rr['BestiaryRecipes.dat']:
            self._copy_from_keys(row, self._COPY_KEYS_BESTIARY, recipes)
            for value in row['BestiaryRecipeComponentKeys']:
                recipe_components_temp[row['Id']][value['Id']] += 1

        for row in self.rr['BestiaryRecipeComponent.dat']:
            self._copy_from_keys(
                row, self._COPY_KEYS_BESTIARY_COMPONENTS, components
            )
            if row['RarityKey'] != RARITY.ANY:
                components[-1]['rarity'] = self.rr['ClientStrings.dat'].index[
                    'Id']['ItemDisplayString' + row['RarityKey'].name_upper][
                    'Text']

        recipe_components = []
        for recipe_id, data in recipe_components_temp.items():
            for component_id, amount in data.items():
                recipe_components.append(OrderedDict((
                    ('recipe_id', recipe_id),
                    ('component_id', component_id),
                    ('amount', amount)
                )))

        r = ExporterResult()
        for k in ('recipes', 'components', 'recipe_components'):
            r.add_result(
                text=lua_formatter(locals()[k]),
                out_file='bestiary_%s.lua' % k,
                wiki_page=[{
                    'page': 'Module:Bestiary/%s' % k,
                    'condition': None,
                }]
            )

        return r


class DelveParser(GenericLuaParser):
    _files = [
        'DelveLevelScaling.dat',
        'DelveResourcePerLevel.dat',
        'DelveUpgrades.dat',
    ]

    _COPY_KEYS_DELVE_LEVEL_SCALING = (
        ('Depth', {
            'key': 'depth',
        }),
        ('MonsterLevel', {
            'key': 'monster_level',
        }),
        ('SulphiteCost', {
            'key': 'sulphite_cost',
        }),
        ('DarknessResistance', {
            'key': 'darkness_resistance',
        }),
        ('LightRadius', {
            'key': 'light_radius',
        }),
        ('MoreMonsterLife', {
            'key': 'monster_life',
        }),
        ('MoreMonsterDamage', {
            'key': 'monster_damage',
        }),
    )

    _COPY_KEYS_DELVE_RESOURCES_PER_LEVEL = (
        ('AreaLevel', {
            'key': 'area_level',
        }),
        ('Sulphite', {
            'key': 'sulphite',
        }),
    )

    _COPY_KEYS_DELVE_UPGRADES = (
        ('DelveUpgradeTypeKey', {
            'key': 'type',
            'value': lambda x: x.name.lower(),
        }),
        ('UpgradeLevel', {
            'key': 'level',
        }),
    )

    def main(self, parsed_args):
        delve_level_scaling = []
        delve_resources_per_level = []
        delve_upgrades = []
        delve_upgrade_stats = []

        for row in self.rr['DelveLevelScaling.dat']:
            self._copy_from_keys(row, self._COPY_KEYS_DELVE_LEVEL_SCALING,
                                 delve_level_scaling)

        for row in self.rr['DelveResourcePerLevel.dat']:
            self._copy_from_keys(row, self._COPY_KEYS_DELVE_RESOURCES_PER_LEVEL,
                                 delve_resources_per_level)

        for row in self.rr['DelveUpgrades.dat']:
            self._copy_from_keys(row, self._COPY_KEYS_DELVE_UPGRADES,
                                 delve_upgrades)
            delve_upgrades[-1]['cost'] = row['Cost']

            for i, (stat, value) in enumerate(row['Stats']):
                self._copy_from_keys(row, self._COPY_KEYS_DELVE_UPGRADES,
                                     delve_upgrade_stats)
                delve_upgrade_stats[-1]['id'] = stat['Id']
                delve_upgrade_stats[-1]['value'] = value

        r = ExporterResult()
        for k in ('level_scaling', 'resources_per_level', 'upgrades',
                  'upgrade_stats'):
            r.add_result(
                text=lua_formatter(locals()['delve_' + k]),
                out_file='delve_%s.lua' % k,
                wiki_page=[{
                    'page': 'Module:Delve/delve_%s' % k,
                    'condition': None,
                }]
            )

        return r


class QuestRewardReader(BaseParser):
    # Load the files we need
    _files = [
        'BaseItemTypes.dat',
        'Characters.dat',
        'NPCs.dat',
        'Quest.dat',
        'QuestStates.dat',
        'QuestRewards.dat',
        'QuestVendorRewards.dat',
        'MapSeries.dat'
    ]

    # TODO find a better way
    # TODO Break with updates
    _ITEM_MAP = {
        'English': {
            # A2: Though Scared Ground
            423: "Survival Instincts", # Veridian
            424: "Survival Skills", # Crimson
            425: "Survival Secrets", # Cobalt
            # A5: The King's Feast
            454: "Poacher's Aim", # Verdian
            455: "Warlord's Reach ", # Crimson
            456: "Assassin's Haste", # Cobalt
            #
            457: "Conqueror's Efficiency", # crimson
            458: "Conqueror's Potency", # cobalt
            459: "Conqueror's Longevity", #viridian
            # A5: Death to Puirty
            560: "Rapid Expansion",
            780: "Wildfire",
            777: "Overwhelming Odds",

            775: "Collateral Damage",
            779: "Omen on the Winds",
            781: "Fight for Survival",
            784: "Ring of Blades",

            778: "First Snow",
            783: "Frozen Trail",
            786: "Inevitability",
            788: "Spreading Rot",
            789: "Violent Dead",
            790: "Hazardous Research",
        },
        'Russian': {
            # A2: По святой земле
            423: "Инстинкты выживания", # Бирюзовый
            424: "Навыки выживания", # Багровый
            425: "Секреты выживания", # Кобальтовый
            # A5: Пир вождя
            454: "Браконьерство", # Бирюзовый
            455: "Длинные руки ", # Багровый
            456: "Бойкий убийца", # Кобальтовый
            #
            457: "Смекалка победителя", # Багровый
            458: "Могущество победителя", # Кобальтовый
            459: "Живучесть победителя", #Бирюзовый
            # A5: Смерть Чистоте
            560: "Быстрое расширение",
            780: "Степной пожар",
            777: "Подавляющее превосходство",

            775: "Сопутствующий риск",
            779: "Знамение ветров",
            781: "Борьба за жизнь",
            784: "Кольцо клинков",

            778: "Первый снег",
            783: "Мерзлый путь",
            786: "Неизбежность",
            788: "Гангрена",
            789: "Ярость мертвецов",
            790: "Опасная наука",
        },
    }

    _TWO_STONE_MAP = {
        'English': {
            'Metadata/Items/Rings/Ring12': "Two-Stone Ring (ruby and topaz)",
            'Metadata/Items/Rings/Ring13': "Two-Stone Ring (sapphire and topaz)",
            'Metadata/Items/Rings/Ring14': "Two-Stone Ring (ruby and sapphire)",
        },
        'Russian': {
            'Metadata/Items/Rings/Ring12':
                "Кольцо с двумя камнями (рубин и топаз)",
            'Metadata/Items/Rings/Ring13':
                "Кольцо с двумя камнями (сапфир и топаз)",
            'Metadata/Items/Rings/Ring14':
                "Кольцо с двумя камнями (рубин и сапфир)",
        },
        'German': {
            'Metadata/Items/Rings/Ring12': "Zweisteinring (Rubin und Topas)",
            'Metadata/Items/Rings/Ring13': "Zweisteinring (Saphir und Topas)",
            'Metadata/Items/Rings/Ring14': "Zweisteinring (Rubin und Saphir)",
        }
    }

    _UNIT_SEP = '\u001F'

    def _write_lua(self, outdata, data_type):
        # Pre-sort
        outdata.sort(key=lambda x: x['reward'])
        outdata.sort(key=lambda x: x['quest_id'])
        outdata.sort(key=lambda x: x['act'])

        r = ExporterResult()
        r.add_result(
            text=lua_formatter(outdata),
            out_file='%s_rewards.txt' % data_type,
            wiki_page=[{
                'page': 'Module:Quest reward/data/%s' % data_type,
                'condition': None,
            }]
        )

        return r

    def read_quest_rewards(self, args):
        compress = {}
        for row in self.rr['QuestRewards.dat']:
            # Find the corresponding keys
            item = row['BaseItemTypesKey']

            # TODO: Skipping random map reward with zana mod here
            if item is None:
                continue
            quest = row['QuestKey']
            character = row['CharactersKey']


            itemcls = item['ItemClassesKey']['Id']

            # Format the data
            data = OrderedDict()

            data['quest'] = quest['Name']
            data['quest_id'] = quest['Id']
            # Quest not implemented or buggy or master stuff
            if not data['quest']:
                continue
            data['act'] = quest['Act']

            if character is not None:
                data['classes'] = character['Name']

            if row['RarityKey'] != RARITY.ANY:
                rarity = self.rr['ClientStrings.dat'].index['Id'][
                    'ItemDisplayString' + row['RarityKey'].name_upper]['Text']

            sockets = row['SocketGems']
            if sockets:
                data['sockets'] = sockets

            name = item['Name']

            # Some of unique items follow special rules
            if itemcls == 'QuestItem' and 'Book' in item['Id']:
                name = '%s (%s)' % (name, data['quest'])
            elif itemcls == 'Map':
                name = '%s (%s)' % (
                    name, self.rr['MapSeries.dat'].index['Id']['MapWorlds'][
                        'Name']
                )
            # Non non quest items or skill gems have their rarity added
            if itemcls not in {'Active Skill Gem', 'Support Skill Gem',
                               'QuestItem', 'StackableCurrency'}:
                data['item_level'] = row['ItemLevel']
                data['rarity'] = rarity
                # Unique and not a quest item or gem
                if row['RarityKey'] == RARITY.ANY:
                    uid = row['Key0']
                    item_map = self._ITEM_MAP.get(config.get_option('language'))
                    if item_map is None:
                        warnings.warn(
                             'No unique item mapping defined for the current '
                             'language'
                        )
                    elif uid in item_map:
                        name = item_map[uid]
                        data['rarity'] = self.rr['ClientStrings.dat'].index[
                            'Id']['ItemDisplayStringUnique']['Text']
                    else:
                        warnings.warn(
                            'Uncaptured unique item. %s %s %s' % (
                                uid, data['quest'], name)
                        )

            # Two stone rings
            two_stone_map = self._TWO_STONE_MAP.get(
                config.get_option('language'))
            if two_stone_map is None:
                warnings.warn(
                    'No two stone ring mapping for the current language')
            elif item['Id'] in two_stone_map:
                name = two_stone_map[item['Id']]
            data['reward'] = name

            # Add to formatting list
            key = quest['Id'] + item['Id'] + str(row['Key0'])
            if key in compress:
                compress[key]['classes'] += self._UNIT_SEP + character['Name']
            else:
                compress[key] = data

        outdata = [data for data in compress.values()]
        return self._write_lua(outdata, 'quest')

    def read_vendor_rewards(self, args):
        compress = {}

        for row in self.rr['QuestVendorRewards.dat']:
            # Find the corresponding keys
            quests = []
            quest_state_key = row['QuestState']

            for quest_state_row in self.rr['QuestStates.dat']:
                if quest_state_key not in quest_state_row['QuestStates']:
                    continue

                quests.append(quest_state_row['QuestKey'])

            if not quests and quest_state_key == 385:
                # Fallen from Grace quest
                quests.append(self.rr['Quest.dat'].index['Id']['a6q4'])

            if not quests:
                warnings.warn(
                    'Row %s: Quest vendor reward had no quest associated; \n'
                    'State: %s\n'
                    'NPC: %s\n'
                    'Items: %s\n' % (
                        row.rowid,
                        quest_state_key,
                        row['NPCKey']['Name'],
                        [i['Name'] for i in row['BaseItemTypesKeys']],
                    )
                )
                continue

            items = row['BaseItemTypesKeys']

            if not items:
                warnings.warn('Row %s: No corresponding items found for given item ids' % row.rowid)
                continue

            classes = row['CharactersKeys']

            # Format the data:

            for quest in quests:
                for item in items:
                    data = OrderedDict()

                    data['quest'] = quest['Name']
                    data['quest_id'] = quest['Id']
                    data['act'] = quest['Act']
                    data['reward'] = item['Name']

                    data['npc'] = row['NPCKey']['Name']

                    if classes:
                        data['classes'] = '\u001F'.join(
                            [cls['Name'] for cls in classes]
                        )

                    key = quest['Id'] + item['Id']
                    if key in compress:
                        if 'classes' in data:
                            compress[key]['classes'] += self._UNIT_SEP + \
                                                        data['classes']
                    else:
                        compress[key] = data

        classes_set = {row['Name'] for row in self.rr['Characters.dat']}

        for k, v in compress.items():
            if 'classes' not in v:
                continue
            classes = set(v['classes'].split(self._UNIT_SEP))
            if len(classes_set.difference(classes)) == 0:
                del v['classes']
            else:
                v['classes'] = self._UNIT_SEP.join(sorted(classes))
        outdata = [data for data in compress.values()]
        return self._write_lua(outdata, 'vendor')


class SynthesisParser(GenericLuaParser):

    _DATA = (
        {
            'file': 'ItemSynthesisCorruptedMods.dat',
            'key': 'synthesis_corrupted_mods',
            'data': (
                ('ItemClassesKey', {
                    'key': 'item_class_id',
                    'value': lambda v: v['Id'],
                }),
                ('ModsKeys', {
                    'key': 'mod_ids',
                    'value': lambda v: [m['Id'] for m in v],
                }),
            ),
        },
        {
            'file': 'ItemSynthesisMods.dat',
            'key': 'synthesis_mods',
            'data': (
                ('StatsKey', {
                    'key': 'stat_id',
                    'value': lambda v: v['Id'],
                }),
                ('StatValue', {
                    'key': 'stat_value',
                }),
                ('ItemClassesKeys', {
                    'key': 'item_class_ids',
                    'value': lambda v: [ic['Id'] for ic in v],
                }),
                ('ModsKeys', {
                    'key': 'mod_ids',
                    'value': lambda v: [m['Id'] for m in v],
                }),
            ),
        },
        {
            'file': 'SynthesisAreas.dat',
            'key': 'synthesis_areas',
            'data': (
                ('Id', {
                    'key': 'id',
                }),
                ('MinLevel', {
                    'key': 'min_level',
                }),
                ('MaxLevel', {
                    'key': 'max_level',
                }),
                ('Weight', {
                    'key': 'weight',
                }),
                ('Name', {
                    'key': 'name',
                }),
                ('SynthesisAreaSizeKey', {
                    'key': 'size',
                    'value': lambda v: v.rowid,
                }),
            ),
        },
        {
            'file': 'SynthesisGlobalMods.dat',
            'key': 'synthesis_global_mods',
            'data': (
                ('ModsKey', {
                    'key': 'mod_id',
                    'value': lambda v: v['Id'],
                }),
                ('MinLevel', {
                    'key': 'min_level',
                }),
                ('MaxLevel', {
                    'key': 'max_level',
                }),
                ('Weight', {
                    'key': 'weight',
                }),
            ),
        },
    )

    _files = [row['file'] for row in _DATA]

    def main(self, parsed_args):
        data = {}
        for definition in self._DATA:
            data[definition['key']] = []
            for row in self.rr[definition['file']]:
                self._copy_from_keys(
                    row, definition['data'], data[definition['key']]
                )

        for row in data['synthesis_mods']:
            row['stat_text'] = \
                '<br>'.join(self.tc['stat_descriptions.txt'].get_translation(
                    tags=(row['stat_id'], ),
                    values=(row['stat_value'], ),
                    lang=self.lang,
                )).replace('\n', '')


        r = ExporterResult()
        for definition in self._DATA:
            key = definition['key']
            r.add_result(
                text=lua_formatter(data[key]),
                out_file='%s.lua' % key,
                wiki_page=[{
                    'page': 'Module:Synthesis/%s' % key,
                    'condition': None,
                }]
            )

        return r


class MonsterParser(GenericLuaParser):
    _DATA = (
        {
            'key': 'monster_types',
            'file': 'MonsterTypes.dat',
            'data': (
                ('Id', {
                    'key': 'id',
                }),
                ('TagsKeys', {
                    'key': 'tags',
                    'value': lambda v: ', '.join([r['Id'] for r in v]),
                }),
                ('MonsterResistancesKey', {
                    'key': 'monster_resistance_id',
                    'value': lambda v: v['Id'],
                }),
                ('Armour', {
                    'key': 'armour_multiplier',
                    'value': lambda v: v/100,
                }),
                ('Evasion', {
                    'key': 'evasion_multiplier',
                    'value': lambda v: v/100,
                }),
                ('EnergyShieldFromLife', {
                    'key': 'energy_shield_multiplier',
                    'value': lambda v: v/100,
                }),
                ('DamageSpread', {
                    'key': 'damage_spread',
                    'value': lambda v: v/100,
                }),
            ),
        },
        {
            'key': 'monster_resistances',
            'file': 'MonsterResistances.dat',
            'data': (
                ('Id', {
                    'key': 'id',
                }),
                ('FireNormal', {
                    'key': 'part1_fire',
                }),
                ('ColdNormal', {
                    'key': 'part1_cold',
                }),
                ('LightningNormal', {
                    'key': 'part1_lightning',
                }),
                ('ChaosNormal', {
                    'key': 'part1_chaos',
                }),
                ('FireCruel', {
                    'key': 'part2_fire',
                }),
                ('ColdCruel', {
                    'key': 'part2_cold',
                }),
                ('LightningCruel', {
                    'key': 'part2_lightning',
                }),
                ('ChaosCruel', {
                    'key': 'part2_chaos',
                }),
                ('FireMerciless', {
                    'key': 'maps_fire',
                }),
                ('ColdMerciless', {
                    'key': 'maps_cold',
                }),
                ('LightningMerciless', {
                    'key': 'maps_lightning',
                }),
                ('ChaosMerciless', {
                    'key': 'maps_chaos',
                }),
            ),
        },
        {
            'key': 'monster_base_stats',
            'file': 'DefaultMonsterStats.dat',
            'data': (
                ('DisplayLevel', {
                    'key': 'level',
                    'value': lambda v: int(v),
                }),
                ('Damage', {
                    'key': 'damage',
                }),
                ('Evasion', {
                    'key': 'evasion',
                }),
                ('Accuracy', {
                    'key': 'accuracy',
                }),
                ('Life', {
                    'key': 'life',
                }),
                ('Experience', {
                    'key': 'experience',
                }),
                ('AllyLife', {
                    'key': 'summon_life',
                }),
            ),
        },
    )

    _ENUM_DATA = {
        'monster_map_multipliers': {
            'MonsterMapDifficulty.dat': (
                ('MapLevel', {
                    'key': 'level',
                }),
                # stat1Key -> map_hidden_monster_life_+%_final
                ('Stat1Value', {
                    'key': 'life',
                }),
                # stat2key -> map_hidden_monster_damage_+%_final
                ('Stat2Value', {
                    'key': 'damage',
                }),
            ),
            'MonsterMapBossDifficulty.dat': (
                # stat1Key -> map_hidden_monster_life_+%_final
                ('Stat1Value', {
                    'key': 'boss_life',
                }),
                # stat2key -> map_hidden_monster_damage_+%_final
                ('Stat2Value', {
                    'key': 'boss_damage',
                }),
                # stat1Key -> monster_dropped_item_quantity_+%
                ('Stat3Value', {
                    'key': 'boss_item_quantity',
                }),
                # stat2key -> monster_dropped_item_rarity_+%
                ('Stat4Value', {
                    'key': 'boss_item_rarity',
                }),
            ),
        },
        'monster_life_scaling': {
            'MagicMonsterLifeScalingPerLevel.dat': (
                ('Level', {
                    'key': 'level',
                }),
                ('Life', {
                    'key': 'magic',
                }),
            ),
            'RareMonsterLifeScalingPerLevel.dat': (
                ('Life', {
                    'key': 'rare',
                }),
            ),
        },
    }

    #_files = [row['files'].keys() in _DATA]

    def main(self, parsed_args):
        data = {}
        for definition in self._DATA:
            data[definition['key']] = []
            for row in self.rr[definition['file']]:
                self._copy_from_keys(
                    row, definition['data'], data[definition['key']]
                )

        for key, data_map in self._ENUM_DATA.items():
            map_multi = []
            for file_name, definition in data_map.items():
                for i, row in enumerate(self.rr[file_name]):
                    self._copy_from_keys(
                        row, definition, map_multi, i
                    )

            data[key] = map_multi

        r = ExporterResult()
        for key, v in data.items():
            r.add_result(
                text=lua_formatter(v),
                out_file='%s.lua' % key,
                wiki_page=[{
                    'page': 'Module:Monster/%s' % key,
                    'condition': None,
                }]
            )

        return r