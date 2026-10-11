"""Reproduce field-supply evidence from the pinned FileDiver data (no game access).

Requires the files named in FIELD_SUPPLIES.md under research/filediver.
Run from the repository root with the same Python runtime as build_overlay.py.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import resource_hash

PIN = 'bf0ce329db3cf0043994eb717ea86433c303cb36'


def type_hash(value):
    result = 5381
    for char in value:
        result = (result * 33 + ord(char)) & 0xffffffff
    return (result - 5381) & 0xffffffff


def evidence():
    folder = ROOT / 'research/filediver'
    library = (folder / 'datalibrary/dl_library.dl_typelib').read_bytes()
    entities = (folder / 'datalibrary/generated_entities.dl_bin').read_bytes()
    _, _, nt, ne, *_ = struct.unpack_from('<4s8I', library)
    ids = struct.unpack_from(f'<{nt}I', library, 36)
    td = 36 + 4 * (nt + ne)
    md = td + 36 * nt + 32 * ne

    def layout(name):
        t = struct.unpack_from('<9I', library, td + 36 * ids.index(type_hash(name)))
        return t[3], [struct.unpack_from('<18I', library, md + 72 * i)
                      for i in range(t[7], t[7] + t[6])]

    def table(name):
        size, (hashmap, records) = layout(name + 'Data')
        stride, _ = layout(name)
        offset = entities.index(b'LDLD' + struct.pack('<II', 1, type_hash(name + 'Data')))
        assert struct.unpack_from('<I', entities, offset + 12)[0] == size
        data = entities[offset + 24:offset + 24 + size]
        result = {}
        for i in range(hashmap[3] >> 16):
            key, index = struct.unpack_from('<QI', data, hashmap[10] + i * 16)
            if key:
                assert index < records[3] >> 16
                start = records[10] + index * stride
                result[key] = data[start:start + stride]
        return result

    units, interactables = table('UnitComponent'), table('InteractableComponent')
    assert layout('InteractableComponent')[1][5][10] == 8  # zones
    assert layout('InteractZoneInfo')[0] == 136
    zone_fields = layout('InteractZoneInfo')[1]
    assert [zone_fields[i][10] for i in (3, 6, 8, 22, 23)] == [12, 40, 45, 100, 101]
    result = []
    for category, prefix, interact_type in [('ammo', 'ammo_box', 4),
                                           ('grenades', 'grenade_box', 6),
                                           ('stims', 'health_pack', 5)]:
        path = f'content/fac_helldivers/discoverables/{prefix}_discoverable_01/{prefix}_discoverable_01'
        key = resource_hash(path)
        model, = struct.unpack_from('<Q', units[key])
        zone = interactables[key][8:144]
        node, = struct.unpack_from('<I', zone, 12)
        assert model == key
        assert struct.unpack_from('<I', zone, 40)[0] == interact_type
        assert (node, zone[45], zone[100], zone[101]) == (0x4a182741, 1, 0, 1)
        assert resource_hash('StingrayEntityRoot') >> 32 == node
        result.append(dict(category=category, entity=f'{key:016x}', model=f'{model:016x}',
                           path=path, node='StingrayEntityRoot', node_hash=f'{node:08x}',
                           interact_type=interact_type, start_enabled=True,
                           delete_after_interact=True,
                           model_consumers=[dict(entity=f'{k:016x}',
                               start_enabled=bool(interactables[k][8 + 45]) if k in interactables else None)
                               for k, value in units.items() if struct.unpack_from('<Q', value)[0] == model]))
    return dict(filediver_commit=PIN,
                typelib_sha256=hashlib.sha256(library).hexdigest(),
                entities_sha256=hashlib.sha256(entities).hexdigest(), supplies=result)


if __name__ == '__main__':
    output = ROOT / 'research/field-supplies.json'
    output.write_text(json.dumps(evidence(), indent=2) + '\n')
    print(output)
