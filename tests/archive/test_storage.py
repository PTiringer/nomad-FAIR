import random
import string

import msgpack
import msgspec.msgpack
import pytest

from nomad.archive.storage_v2 import ArchiveDict, ArchiveList


def generate_random_json(depth=10, width=4, simple=False):
    seed = random.random()

    if depth == 0 or (simple and seed < 0.4):
        return random.choice(
            [
                random.randint(1, 100),
                random.random(),
                random.choice([True, False]),
                ''.join(
                    random.choices(
                        string.ascii_letters + string.digits, k=random.randint(5, 10)
                    )
                ),
            ]
        )

    if seed < 0.7:
        obj = {}
        for _ in range(width):
            key = ''.join(
                random.choices(string.ascii_lowercase, k=random.randint(5, 10))
            )
            value = generate_random_json(depth - 1, width, True)
            obj[key] = value
        return obj

    lst = []
    for _ in range(width):
        value = generate_random_json(depth - 1, width, True)
        lst.append(value)
    return lst


def find_all_paths(json_obj, path=None, paths_list=None):
    if paths_list is None:
        paths_list = []

    if isinstance(json_obj, dict | ArchiveDict):
        for key, value in json_obj.items():
            new_path = [key] if not path else path + [key]
            find_all_paths(value, new_path, paths_list)
    elif isinstance(json_obj, list | ArchiveList):
        for index, value in enumerate(json_obj):
            new_path = [index] if not path else path + [index]
            find_all_paths(value, new_path, paths_list)

    if path:
        paths_list.append(path)

    return paths_list


def to_path(container, path):
    for key in path:
        container = container[key]
    return container


@pytest.fixture(scope='module')
def sample_data():
    return msgpack.dumps(generate_random_json(depth=12, width=6))


@pytest.mark.skip
def test_decode_msgpack(benchmark, sample_data):
    benchmark(msgpack.loads, sample_data)


@pytest.mark.skip
def test_decode_msgspec(benchmark, sample_data):
    benchmark(msgspec.msgpack.decode, sample_data)
