#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import datetime

from fastapi import HTTPException
from mongoengine import DateTimeField, DictField, Document, ListField, StringField
from starlette import status

from nomad.metainfo import Package


class PackageDefinition(Document):
    snapshot_package_id = StringField(
        primary_key=True, regex=r'^\w{40}$', required=True
    )
    date_created = DateTimeField(default=datetime.datetime.now)
    entry_id = StringField(required=True)
    upload_id = StringField(required=True)
    qualified_name = StringField(required=True)
    package_definition = DictField(required=True)
    snapshot_section_ids = ListField(StringField(regex=r'^\w{40}$'), default=None)

    meta = {'indexes': ['snapshot_section_ids']}

    @classmethod
    def create_new(cls, package: Package, **kwargs):
        if package is None:
            return

        fields: dict = dict(
            entry_id=package.entry_id,
            upload_id=package.upload_id,
            qualified_name=package.qualified_name(),
            package_definition=package.m_to_dict(**(dict(with_def_id=True) | kwargs)),
            snapshot_section_ids=[
                section.definition_id for section in package.section_definitions
            ],
            date_created=datetime.datetime.now(),
        )

        target = cls.objects(snapshot_package_id=package.definition_id)

        if target.count() > 0:
            target.update_one(**{f'set__{k}': v for k, v in fields.items()})
        else:
            cls(snapshot_package_id=package.definition_id, **fields).save()

    @classmethod
    def get_by(cls, snapshot_id: str):
        packages = cls.objects(snapshot_section_ids=snapshot_id)

        if packages.count() == 0:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail='Package not found. The given section definition is not contained in any packages.',
            )

        result = packages.first().to_mongo().to_dict()
        result['snapshot_package_id'] = result.pop('_id')

        return result
