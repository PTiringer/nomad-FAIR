import os
import runpy

import pytest

prefix = os.path.join(__file__, '../../../examples/metainfo')


@pytest.mark.parametrize(
    'file',
    [
        f'{prefix}/data_frames.py',
    ],
)
def test_metainfo(file):
    runpy.run_path(file)
