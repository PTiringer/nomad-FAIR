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
import os
import random
import re
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING

import h5py
import numpy as np
import requests
from ase.data import atomic_masses, atomic_numbers, chemical_symbols
from unidecode import unidecode

from nomad.datamodel.metainfo.workflow import Link, Task, Workflow
from nomad.metainfo.data_type import m_str

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger
from nomad import utils
from nomad.datamodel.data import ArchiveSection
from nomad.datamodel.metainfo.annotations import (
    ELNAnnotation,
    Filter,
    HDF5Annotation,
    SectionProperties,
)
from nomad.datamodel.results import ELN, Material, Results
from nomad.datamodel.results import ElementalComposition as ResultsElementalComposition
from nomad.datamodel.util import create_custom_mapping
from nomad.metainfo import Datetime, Quantity, Section, SectionProxy, SubSection
from nomad.metainfo.util import MEnum
from nomad.units import ureg

PUB_CHEM_PUG_PATH = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound'
CAS_API_PATH = 'https://commonchemistry.cas.org/api'
EXTERNAL_API_TIMEOUT = 5


def throttle_wait():
    """Function for waiting before an API request to prevent throttling."""
    time.sleep(random.randint(1, 3))


def pub_chem_add_throttle_header(response: requests.Response, message: str = '') -> str:
    """Function for adding the PubChem PUG API throttling control header to a message."""
    if 'X-Throttling-Control' in response.headers:
        message += f' (Throttling-Control: {response.headers["X-Throttling-Control"]})'
    return message


def pub_chem_api_get_properties(
    cid: int, properties: Iterable[str]
) -> requests.Response:
    """
    Function for performing a get request to the PubChem PUG API to get properties for a
    given compound identifier.

    Args:
        cid (int): The compound identifier of the compound of interest.
        properties (Iterable[str]): The properties to retrieve the value for.

    Returns:
        requests.Response: The response as returned from the PubChem PUG API.
    """
    return requests.get(
        url=f'{PUB_CHEM_PUG_PATH}/cid/{cid}/property/{str.join(",", properties)}/JSON',
        timeout=EXTERNAL_API_TIMEOUT,
    )


def pub_chem_api_get_synonyms(cid: int) -> requests.Response:
    """
    Function for performing a get request to the PubChem PUG API to get properties for a
    given compound identifier.

    Args:
        cid (int): The compound identifier of the compound of interest.

    Returns:
        requests.Response: The response as returned from the PubChem PUG API.
    """
    return requests.get(
        url=f'{PUB_CHEM_PUG_PATH}/cid/{cid}/synonyms/JSON',
        timeout=EXTERNAL_API_TIMEOUT,
    )


def pub_chem_api_search(path: str, search: str) -> requests.Response:
    """
    Function for performing a get request to the PubChem PUG API to search the given path
    for a given string.

    Args:
        path (str): The path (property) to search for.
        search (str): The string to search for a match with.

    Returns:
        requests.Response: The response as returned from the PubChem PUG API.
    """
    return requests.get(
        url=f'{PUB_CHEM_PUG_PATH}/{path}/{search}/cids/JSON',
        timeout=EXTERNAL_API_TIMEOUT,
    )


def cas_api_search(search: str) -> requests.Response:
    """
    Function for performing a get request to the CAS API to search for a match with the
    given string.

    Args:
        search (str): The string to search for a match with.

    Returns:
        requests.Response: The response as returned from the CAS API.
    """
    return requests.get(
        f'{CAS_API_PATH}/search?q={search}',
        timeout=EXTERNAL_API_TIMEOUT,
    )


def cas_api_details(cas_rn: str) -> requests.Response:
    """
    Function for performing a get request to the CAS API to get the details for the
    substance with the given CAS registry number.

    Args:
        cas_rn (str): The CAS registry number of the substance for which to get details.

    Returns:
        requests.Response: The response as returned from the CAS API.
    """
    return requests.get(
        f'{CAS_API_PATH}/detail?cas_rn={cas_rn}',
        timeout=EXTERNAL_API_TIMEOUT,
    )


def is_cas_rn(candidate: str) -> bool:
    """
    Help function for checking if a candidate string is a valid CAS Registry Number.

    Args:
        candidate (str): The candidate string to be checked.

    Returns:
        bool: Whether or not the candidate string is a valid CAS Registry Number.
    """
    try:
        match = re.fullmatch(
            r'(?P<p1>\d{2,7})-(?P<p2>\d{2})-(?P<check>\d{1})', candidate
        )
        check = (
            sum(
                [
                    int(c) * (i + 1)
                    for i, c in enumerate(
                        reversed(match.group('p1') + match.group('p2'))
                    )
                ]
            )
            % 10
        )
        return int(match.group('check')) == check
    except (AttributeError, TypeError):
        return False


class BaseSection(ArchiveSection):
    """
    A generic abstract base section that provides a few commonly used properties.

    If you inherit from this section, but do not need some quantities, list those
    quantities in the `eln.hide` annotation of your inheriting section definition.

    Besides predefining some quantities, these base sections will add some metadata
    to NOMAD's search. A particular example are `tags`, if you define a string
    or enum quantity in your sections named `tags`, its values will be searchable.
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/BFO_0000001'],
    )
    name = Quantity(
        type=str,
        description='A short human readable and descriptive name.',
        a_eln=dict(component='StringEditQuantity', label='name'),
    )
    datetime = Quantity(
        type=Datetime,
        description='The date and time associated with this section.',
        a_eln=dict(component='DateTimeEditQuantity'),
    )
    lab_id = Quantity(
        type=str,
        description="""An ID string that is unique at least for the lab that produced this
            data.""",
        a_eln=dict(component='StringEditQuantity', label='ID'),
    )
    description = Quantity(
        type=str,
        description='Any information that cannot be captured in the other fields.',
        a_eln=dict(component='RichTextEditQuantity'),
    )


class Entity(BaseSection):
    """
    An object that persists, endures, or continues to exist through time while maintaining
    its identity.
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/BFO_0000002'],
    )


class ActivityStep(ArchiveSection):
    """
    Any dependant step of an `Activity`.
    """

    m_def = Section()
    name = Quantity(
        type=str,
        description="""
        A short and descriptive name for this step.
        """,
        a_eln=ELNAnnotation(
            component='StringEditQuantity',
            label='step name',
        ),
    )
    start_time = Quantity(
        type=Datetime,
        description="""
        Optionally, the starting time of the activity step. If omitted, it is assumed to
        follow directly after the previous step.
        """,
        a_eln=ELNAnnotation(component='DateTimeEditQuantity', label='starting time'),
    )
    description = Quantity(
        type=str,
        description="""
        Any additional information about the step not captured by the other fields.
        """,
        a_eln=ELNAnnotation(
            component='RichTextEditQuantity',
        ),
    )

    def to_task(self) -> Task:
        """
        Returns the task description of this activity step.

        Returns:
            Task: The activity step as a workflow task.
        """
        return Task(name=self.name)


class Activity(BaseSection):
    """
    An action that has a temporal extension and for some time depends on some entity.
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/BFO_0000015'],
    )
    datetime = Quantity(
        type=Datetime,
        description='The date and time when this activity was started.',
        a_eln=dict(component='DateTimeEditQuantity', label='starting time'),
    )
    method = Quantity(
        type=str,
        description='A short consistent handle for the applied method.',
    )
    location = Quantity(
        type=str,
        description='location of the experiment.',
        a_eln=dict(component='StringEditQuantity'),
    )
    steps = SubSection(
        section_def=ActivityStep,
        description="""
        An ordered list of all the dependant steps that make up this activity.
        """,
        repeats=True,
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `Activity` class.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)

        if archive.results.eln.methods is None:
            archive.results.eln.methods = []
        if self.method:
            archive.results.eln.methods.append(self.method)
        else:
            archive.results.eln.methods.append(self.m_def.name)
        if archive.workflow2 is None:
            archive.workflow2 = Workflow(name=self.name)
        archive.workflow2.tasks = [step.to_task() for step in self.steps]


class SectionReference(ArchiveSection):
    """
    A section used for referencing another section.
    """

    name = Quantity(
        type=str,
        description='A short descriptive name for the role of this reference.',
        a_eln=ELNAnnotation(
            component='StringEditQuantity',
        ),
    )
    reference = Quantity(
        type=ArchiveSection,
        description='A reference to a NOMAD archive section.',
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
            label='section reference',
        ),
    )


class EntityReference(SectionReference):
    """
    A section used for referencing an Entity.
    """

    reference = Quantity(
        type=Entity,
        description='A reference to a NOMAD `Entity` entry.',
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
            label='entity reference',
        ),
    )
    lab_id = Quantity(
        type=str,
        description="""
        The readable identifier for the entity.
        """,
        a_eln=ELNAnnotation(component='StringEditQuantity'),
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `EntityReference` class.
        Will attempt to fill the `reference` from the `lab_id` or vice versa.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        if self.reference is None and self.lab_id is not None:
            from nomad.search import MetadataPagination, search

            query = {'results.eln.lab_ids': self.lab_id}
            search_result = search(
                owner='all',
                query=query,
                pagination=MetadataPagination(page_size=1),
                user_id=archive.metadata.main_author.user_id,
            )
            if search_result.pagination.total > 0:
                entry_id = search_result.data[0]['entry_id']
                upload_id = search_result.data[0]['upload_id']
                self.reference = f'../uploads/{upload_id}/archive/{entry_id}#data'
                if search_result.pagination.total > 1:
                    logger.warn(
                        f'Found {search_result.pagination.total} entries with lab_id: '
                        f'"{self.lab_id}". Will use the first one found.'
                    )
            else:
                logger.warn(f'Found no entries with lab_id: "{self.lab_id}".')
        elif self.lab_id is None and self.reference is not None:
            self.lab_id = self.reference.lab_id
        if self.name is None and self.lab_id is not None:
            self.name = self.lab_id


class ExperimentStep(ActivityStep):
    """
    Any dependant step of an `Experiment`.
    """

    lab_id = Quantity(
        type=str,
        description="""
        The readable identifier for the activity.
        """,
        a_eln=ELNAnnotation(
            component='StringEditQuantity',
            label='activity ID',
        ),
    )
    activity = Quantity(
        type=Activity,
        description="""
        The activity that makes up this step of the experiment.
        """,
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
        ),
    )


class NestedExperimentStep(ExperimentStep):
    """
    A step of an Experiment.

    This class is a wrapper for the `Activity` class and is used to describe
    the metadata of an activity when it is a step of another, larger, experiment.

    The `Activity` class instance can be instantiated in the `activity` property
    as a nested subsection.

    A normalizer will create a link in the activity property inherited from
    the ExperimentStep class.

    """

    m_def = Section(
        a_eln=ELNAnnotation(
            properties=SectionProperties(
                visible=Filter(
                    exclude=[
                        'activity',
                    ],
                ),
            )
        )
    )

    nested_activity = SubSection(
        section_def=Activity,
        description="""
        Section describing the activity that is the step on an experiment.
        """,
        label='activity',
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        super().normalize(archive, logger)

        if self.nested_activity:
            self.activity = self.nested_activity


class Experiment(Activity):
    """
    A section for grouping activities together into an experiment.
    """

    steps = SubSection(
        section_def=ExperimentStep,
        description="""
        An ordered list of all the dependant steps that make up this experiment.
        """,
        repeats=True,
    )


class Collection(Entity):
    """
    A section for grouping entities together into a collection.
    """

    entities = SubSection(
        section_def=EntityReference,
        description='References to the entities that make up the collection.',
        repeats=True,
    )


class ElementalComposition(ArchiveSection):
    """
    A section for describing the elemental composition of a system, i.e. the element
    and its atomic fraction.
    """

    m_def = Section(
        label_quantity='element',
    )
    element = Quantity(
        type=MEnum(chemical_symbols[1:]),
        description="""
        The symbol of the element, e.g. 'Pb'.
        """,
        a_eln=dict(component='AutocompleteEditQuantity'),
    )
    atomic_fraction = Quantity(
        type=np.float64,
        description="""
        The atomic fraction of the element in the system it is contained within.
        Per definition a positive value less than or equal to 1.
        """,
        a_eln=dict(component='NumberEditQuantity'),
    )
    mass_fraction = Quantity(
        type=np.float64,
        description="""
        The mass fraction of the element in the system it is contained within.
        Per definition a positive value less than or equal to 1.
        """,
        a_eln=dict(component='NumberEditQuantity'),
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `ElementalComposition` class. Will add a
        results.material subsection if none exists. Will append the element to the
        elements property of that subsection and a
        nomad.datamodel.results.ElementalComposition instances to the
        elemental_composition property  using the element and atomic fraction from this
        section.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)

        if self.element:
            if not archive.results:
                archive.results = Results()
            if not archive.results.material:
                archive.results.material = Material()

            if self.element not in chemical_symbols:
                logger.warn(
                    f"'{self.element}' is not a valid element symbol and this "
                    'elemental_composition section will be ignored.'
                )
            elif self.element not in archive.results.material.elements:
                archive.results.material.elements += [self.element]
            if self.atomic_fraction or self.mass_fraction:
                comp_result_section = archive.results.material.elemental_composition
                result_composition = ResultsElementalComposition(
                    element=self.element,
                    atomic_fraction=self.atomic_fraction,
                    mass_fraction=self.mass_fraction,
                    mass=atomic_masses[atomic_numbers[self.element]] * ureg.amu,
                )
                existing_elements = [comp.element for comp in comp_result_section]
                if self.element in existing_elements:
                    index = existing_elements.index(self.element)
                    comp_result_section[index].atomic_fraction = self.atomic_fraction
                    comp_result_section[index].mass_fraction = self.mass_fraction
                    comp_result_section[index].mass = (
                        atomic_masses[atomic_numbers[self.element]] * ureg.amu
                    )
                else:
                    comp_result_section.append(result_composition)


class GeometricalSpace(ArchiveSection):
    """
    Geometrical shape attributes of a system.
    Sections derived from `Geometry` represent concrete geometrical shapes.
    """

    m_def = Section()
    # volume = Quantity(
    #     type=float,
    #     description='The measure of the amount of space occupied in 3D space.',
    #     a_eln=ELNAnnotation(
    #         component=ELNComponentEnum.NumberEditQuantity,
    #     ),
    #     unit='meter ** 3',
    # )


class System(Entity):
    """
    A base section for any system of materials which is investigated or used to construct
    other systems.
    """

    # elemental_composition = SubSection(
    #     description="""
    #     A list of all the elements found in the system together and their respective
    #     atomic fraction within the system.
    #     """,
    #     section_def=ElementalComposition,
    #     repeats=True,
    # )

    formula = Quantity(
        type=str,
        description='Molecular formula.',
        a_eln=dict(component='StringEditQuantity'),
    )

    sub_systems = SubSection(
        section_def=SectionProxy('SubSystem'),
        description="""
        A list of all the components that make up the system.
        """,
        repeats=True,
    )

    geometry = SubSection(
        section_def=GeometricalSpace,
        description="""
        Geometrical description of the system.
        The children of GeometricalSpace can describe the macroscopic or microscopic
        geometry of the system.
        """,
    )


class SystemReference(EntityReference):
    """
    A section used for referencing a System into an Activity.
    """

    reference = Quantity(
        type=System,
        description='A reference to a NOMAD `System` entry.',
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
            label='composite system reference',
        ),
    )


class Element(System):
    """
    A base section to define each atom state information.
    """

    m_def = Section(
        label_quantity='element',
    )
    chemical_symbol = Quantity(
        type=MEnum(chemical_symbols[1:]),
        description="""
        The symbol of the element, e.g. 'Pb'.
        """,
        a_eln=dict(component='AutocompleteEditQuantity'),
    )
    atomic_number = Quantity(
        type=np.int32,
        description="""
        Atomic number Z. This quantity is equivalent to `chemical_symbol`.
        """,
    )
    charge = Quantity(
        type=np.int32,
        default=0,
        description="""
        Charge of the atom. It is defined as the number of extra electrons or holes in the
        atom. If the atom is neutral, charge = 0 and the summation of all (if available) the`OrbitalsState.occupation`
        coincides with the `atomic_number`. Otherwise, charge can be any positive integer (+1, +2...)
        for cations or any negative integer (-1, -2...) for anions.

        Note: for `CoreHole` systems we do not consider the charge of the atom even if
        we do not store the final `OrbitalsState` where the electron was excited to.
        """,
        a_eln=ELNAnnotation(component='NumberEditQuantity'),
    )


class PureSubstance(System):
    """
    A sub section for describing any elemental, molecular or single phase pure substance.
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/CHEBI_23367'],
    )
    name = Quantity(
        type=str,
        description='The name of the substance entry.',
        a_eln=dict(component='StringEditQuantity', label='substance name'),
    )
    lab_id = Quantity(
        type=str,
        description="""
        A human human readable substance ID that is at least unique for the lab.
        """,
        a_eln=dict(component='StringEditQuantity', label='substance ID'),
    )
    description = Quantity(
        type=str,
        description="""
        A field for adding additional information about the substance that is not captured
        by the other quantities and subsections.
        """,
        a_eln=dict(
            component='RichTextEditQuantity',
            label='detailed substance description',
        ),
    )
    iupac_name = Quantity(
        type=str,
        description='IUPAC name.',
        a_eln=dict(component='StringEditQuantity'),
    )
    chemical_formula = Quantity(
        type=str,
        description="""
        The chemical formula of the substance.
          """,
        a_eln=dict(component='StringEditQuantity'),
    )
    molar_mass = Quantity(
        type=np.dtype(np.float64),
        unit='g/mol',
        description="""The molar mass is the ratio of the mass of a molecule
        to the unified atomic mass unit.
        Sometimes  molar mass is called molecular weight or relative molar mass.
        https://goldbook.iupac.org/terms/view/R05271
        """,
        a_eln=dict(
            component='NumberEditQuantity',
            defaultDisplayUnit='g/mol',
        ),
    )
    inchi = Quantity(
        type=str,
        description='Inchi.',
        a_eln=dict(component='StringEditQuantity'),
    )
    inchi_key = Quantity(
        type=str,
        description='Inchi key.',
        a_eln=dict(component='StringEditQuantity'),
    )
    smile = Quantity(
        type=str,
        description='Smile.',
        a_eln=dict(component='StringEditQuantity'),
    )
    canonical_smile = Quantity(
        type=str,
        description='Canonical smile.',
        a_eln=dict(component='StringEditQuantity'),
    )
    cas_number = Quantity(
        type=str,
        description='CAS number.',
        a_eln=dict(component='StringEditQuantity'),
    )
    pub_chem_cid = Quantity(
        type=int,
        a_eln=dict(
            component='NumberEditQuantity',
        ),
    )
    pub_chem_link = Quantity(
        type=str,
        a_eln=dict(
            component='StringEditQuantity',
        ),
    )

    def _populate_from_cid(self, logger: 'BoundLogger') -> None:
        """
        Private method for populating unfilled properties by searching the PubChem using
        the CID in `pub_chem_cid`.

        Args:
            logger (BoundLogger): A structlog logger.
        """
        properties = {
            'Title': 'name',
            'IUPACName': 'iupac_name',
            'MolecularFormula': 'molecular_formula',
            'ExactMass': 'molecular_mass',
            'MolecularWeight': 'molar_mass',
            'MonoisotopicMass': 'monoisotopic_mass',
            'InChI': 'inchi',
            'InChIKey': 'inchi_key',
            'IsomericSMILES': 'smile',
            'CanonicalSMILES': 'canonical_smile',
        }
        types = {  # Needed because PubChems API sometimes returns floats as strings
            'Title': str,
            'IUPACName': str,
            'MolecularFormula': str,
            'ExactMass': float,
            'MolecularWeight': float,
            'MonoisotopicMass': float,
            'InChI': str,
            'InChIKey': str,
            'IsomericSMILES': str,
            'CanonicalSMILES': str,
        }
        response = pub_chem_api_get_properties(
            cid=self.pub_chem_cid, properties=properties
        )
        if not response.ok:
            msg = f'Property request to PubChem responded with: {response}'
            logger.warn(pub_chem_add_throttle_header(response, msg))
            return
        self.pub_chem_link = (
            f'https://pubchem.ncbi.nlm.nih.gov/compound/{self.pub_chem_cid}'
        )
        try:
            property_values = response.json()['PropertyTable']['Properties'][0]
        except (KeyError, IndexError):
            property_values = {}
        for property_name in properties:  # noqa
            if getattr(self, properties[property_name], None) is None:
                try:
                    property_value = property_values[property_name]
                    if not isinstance(property_value, types[property_name]):
                        property_value = types[property_name](property_value)
                    setattr(
                        self,
                        properties[property_name],
                        property_value,
                    )
                except KeyError:
                    logger.warn(
                        f'Property "{property_name}" missing from PubChem response.'
                    )
                except ValueError:
                    logger.warn(
                        f'Property "{property_name}" in PubChem response is not of '
                        f'the expected type "{types[property_name]}".'
                    )
        if self.cas_number is None:
            response = pub_chem_api_get_synonyms(cid=self.pub_chem_cid)
            if not response.ok:
                msg = f'Synonyms request to PubChem responded with: {response}'
                logger.warn(pub_chem_add_throttle_header(response, msg))
                return
            response_dict = response.json()
            try:
                synonyms = response_dict['InformationList']['Information'][0]['Synonym']
            except (KeyError, IndexError):
                synonyms = []
            for synonym in synonyms:
                if is_cas_rn(synonym):
                    self.cas_number = synonym
                    break

    def _pub_chem_search_unique(
        self, search: str, path: str, logger: 'BoundLogger'
    ) -> bool:
        """
        Private method for searching the PubChem API for CIDs using the provided `path`
        and `search` strings.

        Args:
            search (str): The string containing the search value.
            path (str): The path to search the string for.
            logger (BoundLogger): A structlog logger.

        Returns:
            bool: _description_
        """
        response = pub_chem_api_search(path=path, search=search)
        if response.status_code == 404:
            logger.info(f'No results for PubChem search for {path}="{search}".')
            return False
        elif not response.ok:
            logger.warn(f'PubChem search for {path}="{search}" yielded: {response}')
            return False
        try:
            cids = response.json()['IdentifierList']['CID']
        except KeyError:
            logger.warn(f'CID search request to PubChem response missing CID list.')
            return False
        if len(cids) == 0:
            return False
        elif len(cids) > 1:
            urls = [f'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}' for cid in cids]
            logger.warn(
                f'Search for PubChem CID yielded {len(cids)} results: '
                f'{", ".join(urls)}. Using {urls[0]}'
            )
        self.pub_chem_cid = cids[0]
        return True

    def _find_cid(self, logger: 'BoundLogger') -> None:
        """
        Private method for finding the PubChem CID using the filled attributes in the
        following order:

        1. `smile`
        2. `canonical_smile`
        3. `inchi_key`
        4. `iupac_name`
        5. `name`
        6. `molecular_formula`

        The first hit will populate the `pub_chem_cid` attribute and return.

        Args:
            logger ('BoundLogger'): A structlog logger.
        """
        for search, path in (
            (self.smile, 'smiles'),
            (self.canonical_smile, 'smiles'),
            (self.inchi_key, 'inchikey'),
            (self.iupac_name, 'name'),
            (self.name, 'name'),
            (self.molecular_formula, 'fastformula'),
            # (self.name, 'fastformula'),
            # gives error 500 when a non existing ff is used
            (self.cas_number, 'name'),
        ):
            if search and self._pub_chem_search_unique(search, path, logger):
                self._populate_from_cid(logger)

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer method for the `PureSubstance` class.

        This method will:
        - populate the results.material section and the elemental
        composition sub section using the molecular formula.
        - attempt to get data on the substance instance from the PubChem
        PUG REST API: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
        If a PubChem CID is specified the details are retrieved directly.
        Otherwise a search query is made for the filled attributes in the following order:
        1. `smile`
        2. `canonical_smile`
        3. `inchi_key`
        4. `iupac_name`
        5. `name`
        6. `molecular_formula`
        7. `cas_number`

        Args:
            archive (EntryArchive): The archive that is being normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        #     if logger is None:
        #         logger = utils.get_logger(__name__)
        #     if self.molecular_formula:
        #         if not archive.results:
        #             archive.results = Results()
        #         if not archive.results.material:
        #             archive.results.material = Material()
        #         try:
        #             formula = Formula(self.molecular_formula)
        #             try:
        #                 formula.populate(archive.results.material)
        #             except ValueError:
        #                 logger.info('Not overwriting existing results.material.')
        #             if not self.elemental_composition:
        #                 self.elemental_composition = elemental_composition_from_formula(
        #                     formula
        #                 )
        #         except Exception as e:
        #             logger.warn('Could not analyse chemical formula.', exc_info=e)
        if self.pub_chem_cid:
            if any(getattr(self, value) is None for value in self.m_def.all_quantities):
                self._populate_from_cid(logger)
        else:
            self._find_cid(logger)


# def elemental_composition_from_formula(formula: Formula) -> List[ElementalComposition]:
#     """
#     Help function for generating list of `ElementalComposition` instances from
#     `nomad.atomutils.Formula` item

#     Args:
#         formula (Formula): The `nomad.atomutils.Formula` item

#     Returns:
#         List[ElementalComposition]: List of filled `ElementalComposition` items
#     """
#     mass_fractions = formula.mass_fractions()
#     return [
#         ElementalComposition(
#             element=element,
#             atomic_fraction=fraction,
#             mass_fraction=mass_fractions[element],
#         )
#         for element, fraction in formula.atomic_fractions().items()
#     ]


class SubSystemProperties(ArchiveSection):
    """
    A section for describing the EXTRINSIC properties of a `System`
    when it is part of a larger System.
    Note: the intrinsic properties, i.e., the ones that are not dependent on the
    role of the System as a SubSystem, are described in the `System` class.

    The main example of extrinsic properties is the concentration
    of a subsystem in a solution.
    """

    mass = Quantity(
        type=np.float64,
        description='The mass of the component.',
        unit='kg',
        a_eln=dict(component='NumberEditQuantity', defaultDisplayUnit='mg'),
    )
    atomic_fraction = Quantity(
        type=np.float64,
        description="""
        The atomic fraction of the element in the system it is contained within.
        Per definition a positive value less than or equal to 1.
        """,
        a_eln=dict(component='NumberEditQuantity'),
    )
    mass_fraction = Quantity(
        type=np.float64,
        description="""
        The mass fraction of the element in the system it is contained within.
        Per definition a positive value less than or equal to 1.
        """,
        a_eln=dict(component='NumberEditQuantity'),
    )


class SubSystem(ArchiveSection):
    """
    A component of a system.

    This class is a wrapper for the `System` class and is used to describe
    the metadata of a system when it is a component of another, larger, system.

    The `System` class instance can be included in the `system` property
    as a referenced external archive.

    """

    name = Quantity(
        type=str,
        description='A short name for the sub system.',
        a_eln=dict(component='StringEditQuantity'),
    )
    system = Quantity(
        type=System,
        description='A reference to the component system.',
        a_eln=dict(component='ReferenceEditQuantity'),
    )
    subsystem_properties = SubSection(
        section_def=SubSystemProperties,
        description="""
        Section describing the properties of the sub system.
        """,
    )


class NestedSubSystem(SubSystem):
    """
    A component of a system.

    This class is a wrapper for the `System` class and is used to describe
    the metadata of a system when it is a component of another, larger, system.

    The `System` class instance can be instantiated in the `system` property
    as a nested subsection.

    A normalizer will create a link in the system property inherited from
    the SubSystem class.

    """

    m_def = Section(
        a_eln=ELNAnnotation(
            properties=SectionProperties(
                visible=Filter(
                    exclude=[
                        'system',
                    ],
                ),
            )
        )
    )

    nested_system = SubSection(
        section_def=System,
        description="""
        Section describing the system that is the component.
        """,
        label='system',
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        super().normalize(archive, logger)

        if self.nested_system:
            self.system = self.nested_system


class Instrument(Entity):
    """
    A base section that can be used for instruments.
    """

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `Instrument` class.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)

        if self.name:
            if archive.results.eln.instruments is None:
                archive.results.eln.instruments = []
            archive.results.eln.instruments.append(self.name)


class InstrumentReference(EntityReference):
    """
    A section used for referencing an Instrument.
    """

    reference = Quantity(
        type=Instrument,
        description='A reference to a NOMAD `Instrument` entry.',
        a_eln=ELNAnnotation(
            component='ReferenceEditQuantity',
            label='instrument reference',
        ),
    )


class ProcessStep(ActivityStep):
    """
    Any dependant step of a `Process`.
    """

    duration = Quantity(
        type=float,
        unit='second',
        description="""
        The duration time of the process step.
        """,
        a_eln=ELNAnnotation(
            component='NumberEditQuantity',
            defaultDisplayUnit='second',
        ),
    )


class Process(Activity):
    """
    A planned process which results in physical changes in a specified input material.
    [ obi : prs obi : mc obi : fg obi : jf obi : bp ]

    Synonyms:
     - preparative method
     - sample preparation
     - sample preparative method
     - material transformations
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/OBI_0000094'],
    )
    end_time = Quantity(
        type=Datetime,
        description='The date and time when this process was finished.',
        a_eln=dict(component='DateTimeEditQuantity', label='ending time'),
    )
    steps = SubSection(
        section_def=ProcessStep,
        description="""
        An ordered list of all the dependant steps that make up this activity.
        """,
        repeats=True,
    )
    instruments = SubSection(
        section_def=InstrumentReference,
        description="""
        A list of all the instruments and their role in this process.
        """,
        repeats=True,
    )
    samples = SubSection(
        section_def=SystemReference,
        description="""
        The samples as that have undergone the process.
        """,
        repeats=True,
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `Process` class.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        if (
            self.datetime is not None
            and all(step.duration is not None for step in self.steps)
            and any(step.start_time is None for step in self.steps)
        ):
            start = self.datetime
            for step in self.steps:
                if step.start_time is None:
                    step.start_time = start
                start += datetime.timedelta(seconds=step.duration.magnitude)
            if self.end_time is None and start > self.datetime:
                self.end_time = start
        archive.workflow2.outputs = [
            Link(name=sample.name, section=sample.reference) for sample in self.samples
        ]


class ActivityResult(ArchiveSection):
    """
    A section for the results of an `Activity`.
    """

    name = Quantity(
        type=str,
        description='A short and descriptive name for the result.',
        a_eln=dict(component='StringEditQuantity', label='name'),
    )


class AnalysisResult(ActivityResult):
    """
    A section for the results of an `Analysis` process.
    """

    pass


class Analysis(Activity):
    """
    A planned process that produces output data from input data.

    Synonyms:
     - data processing
     - data analysis
    """

    m_def = Section(links=['http://purl.obolibrary.org/obo/OBI_0200000'])
    inputs = SubSection(
        section_def=SectionReference,
        description='The input data of the analysis.',
        repeats=True,
    )
    outputs = SubSection(
        section_def=AnalysisResult,
        description='The output data of the analysis.',
        repeats=True,
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `Analysis` section.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        archive.workflow2.inputs = [
            Link(name=input.name, section=input.reference) for input in self.inputs
        ]
        archive.workflow2.outputs = [
            Link(name=output.name, section=output) for output in self.outputs
        ]


class SynthesisMethod(Process):
    """
    A method used to synthesise a sample.
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/CHMO_0001301'],
    )


class MeasurementResult(ActivityResult):
    """
    A section for the results of an `Measurement` process.
    """

    pass


class Measurement(Activity):
    """
    A planned process with the objective to produce information about the material entity
    that is the evaluant, by physically examining it or its proxies. [ obi : pppb ]
    """

    m_def = Section(
        links=['http://purl.obolibrary.org/obo/OBI_0000070'],
    )
    samples = SubSection(
        section_def=SystemReference,
        description="""
        A list of all the samples measured during the measurement.
        """,
        repeats=True,
    )
    instruments = SubSection(
        section_def=InstrumentReference,
        description="""
        A list of all the instruments and their role in this process.
        """,
        repeats=True,
    )
    results = SubSection(
        section_def=MeasurementResult,
        description="""
        The result of the measurement.
        """,
        repeats=True,
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `Measurement` section.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        archive.workflow2.inputs = [
            Link(name=sample.name, section=sample.reference) for sample in self.samples
        ]
        archive.workflow2.outputs = [
            Link(name=result.name, section=result) for result in self.results
        ]


class ReadableIdentifiers(ArchiveSection):
    """
    A base section that can be used to generate readable IDs.
    If the `owner`, `short_name`, `institute`, and `datetime`
    quantities are provided, the lab_id will be automatically created as a combination
    of these four quantities.
    """

    institute = Quantity(
        type=str,
        description="""
        Alias/short name of the home institute of the owner, i.e. *HZB*.
        """,
        a_eln=dict(component='StringEditQuantity'),
    )
    owner = Quantity(
        type=str,
        shape=[],
        description="""
        Alias for the owner of the identified thing. This should be unique within the
        institute.
        """,
        a_eln=dict(component='StringEditQuantity'),
    )
    datetime = Quantity(
        type=Datetime,
        description="""
        A datetime associated with the identified thing. In case of an `Activity`, this
        should be the starting time and, in case of an `Entity`, the creation time.
        """,
        a_eln=dict(component='DateTimeEditQuantity'),
    )
    short_name = Quantity(
        type=str,
        description="""
        A short name of the the identified thing (e.g. the identifier scribed on the
        sample, the process number, or machine name), e.g. 4001-8, YAG-2-34.
        This is to be managed and decided internally by the labs, although we recommend
        to avoid the following characters in it: "_", "/", "\\" and ".".
        """,
        a_eln=dict(component='StringEditQuantity'),
    )
    lab_id = Quantity(
        type=str,
        description="""
        Full readable id. Ideally a human readable id convention, which is simple,
        understandable and still have chances of becoming unique.
        If the `owner`, `short_name`, `ìnstitute`, and `datetime` are provided, this will
        be formed automatically by joining these components by an underscore (_).
        Spaces in any of the individual components will be replaced with hyphens (-).
        An example would be hzb_oah_20200602_4001-08.
        """,
        a_eln=dict(component='StringEditQuantity'),
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `ReadableIdentifiers` class.
        If owner is not filled the field will be filled by the first two letters of
        the first name joined with the first two letters of the last name of the author.
        If the institute is not filled a institute abreviations will be constructed from
        the author's affiliation.
        If no datetime is filled, the datetime will be taken from the `datetime`
        property of the parent, if it exists, otherwise the current date and time will be
        used.
        If no short name is filled, the name will be taken from the parent name, if it
        exists, otherwise it will be taken from the archive metadata entry name, if it
        exists, and finally if no other options are available it will use the name of the
        mainfile.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)

        if self.owner is None or self.institute is None:
            author = archive.metadata.main_author
            if author and self.owner is None:
                first_short = unidecode(author.first_name)[:2]
                last_short = unidecode(author.last_name)[:2]
                self.owner = first_short + last_short
            if author and self.institute is None and author.affiliation:
                unwanted_words = ('zu', 'of', 'the', 'fur', 'für')
                institute = ''
                all_words = re.split(' |-|_|,|:|;', unidecode(author.affiliation))
                wanted_words = [w for w in all_words if w.lower() not in unwanted_words]
                for word in wanted_words:
                    word_remainder = word
                    while word_remainder and len(institute) < 3:
                        letter = word_remainder[:1]
                        if letter.isupper():
                            institute += letter
                        word_remainder = word_remainder[1:]
                if len(institute) < min(len(author.affiliation), 2):
                    if len(wanted_words) < 3:
                        institute = author.affiliation[:3].upper()
                    else:
                        institute = ''.join([w[:1] for w in wanted_words[:3]]).upper()
                self.institute = institute

        if self.datetime is None:
            if self.m_parent and getattr(self.m_parent, 'datetime', None):
                self.datetime = self.m_parent.datetime
            else:
                self.datetime = datetime.datetime.now()

        if self.short_name is None:
            if self.m_parent and getattr(self.m_parent, 'name', None):
                name = self.m_parent.name
            elif archive.metadata.entry_name:
                name = archive.metadata.entry_name
            else:
                name = archive.metadata.mainfile
            self.short_name = re.sub(r'_|\s', '-', name.split('.')[0])

        if self.institute and self.short_name and self.owner and self.datetime:
            creation_date = self.datetime.strftime('%Y%m%d')
            owner = self.owner.replace(' ', '-')
            lab_id_list = [self.institute, owner, creation_date, self.short_name]
            self.lab_id = '_'.join(lab_id_list)

        if not archive.results:
            archive.results = Results(eln=ELN())
        if not archive.results.eln:
            archive.results.eln = ELN()

        if self.lab_id:
            if not archive.results.eln.lab_ids:
                archive.results.eln.lab_ids = []
            if self.lab_id not in archive.results.eln.lab_ids:
                archive.results.eln.lab_ids.append(self.lab_id)

        if not archive.results.eln.sections:
            archive.results.eln.sections = []
        archive.results.eln.sections.append(self.m_def.name)


class PublicationReference(ArchiveSection):
    """
    A base section that can be used for references.
    """

    DOI_number = Quantity(
        type=str,
        shape=[],
        description="""
            The DOI number referring to the published paper or dataset where the data can be found.
            Examples:
            10.1021/jp5126624
            10.1016/j.electacta.2017.06.032
        """,
        a_eln=dict(component='EnumEditQuantity', props=dict(suggestions=[])),
    )

    publication_authors = Quantity(
        type=str,
        shape=['*'],
        description="""
            The authors of the publication.
            If several authors, end with et al. If the DOI number is given correctly,
            this will be extracted automatically from www.crossref.org
        """,
    )
    publication_date = Quantity(
        type=Datetime,
        shape=[],
        description="""
            Publication date.
            If the DOI number is given correctly,
            this will be extracted automatically from www.crossref.org
        """,
    )
    journal = Quantity(
        type=str,
        shape=[],
        description="""
            Name of the journal where the data is published.
            If the DOI number is given correctly,
            this will be extracted automatically from www.crossref.org
        """,
    )
    publication_title = Quantity(
        type=str,
        shape=[],
        description="""
            Title of the publication.
            If the DOI number is given correctly,
            this will be extracted automatically from www.crossref.org
        """,
    )

    def normalize(self, archive, logger: 'BoundLogger') -> None:
        """
        The normalizer for the `PublicationReference` class.

        Args:
            archive (EntryArchive): The archive containing the section that is being
            normalized.
            logger ('BoundLogger'): A structlog logger.
        """
        super().normalize(archive, logger)
        import dateutil.parser
        import requests

        from nomad.datamodel.datamodel import EntryMetadata

        # Parse journal name, lead author and publication date from crossref
        if self.DOI_number:
            try:
                url = f'https://api.crossref.org/works/{self.DOI_number}?mailto=contact@nomad-lab.eu'
                timeout = 5
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200:
                    temp_dict = r.json()
                    # make sure the doi has the prefix https://doi.org/
                    if self.DOI_number.startswith('10.'):
                        self.DOI_number = 'https://doi.org/' + self.DOI_number
                    self.publication_authors = [
                        f'{v["given"]} {v["family"]}'
                        for v in temp_dict['message']['author']
                    ]
                    self.journal = temp_dict['message']['container-title'][0]
                    self.publication_title = temp_dict['message']['title'][0]
                    self.publication_date = dateutil.parser.parse(
                        temp_dict['message']['created']['date-time']
                    )
                    if not archive.metadata:
                        archive.metadata = EntryMetadata()
                    if not archive.metadata.references:
                        archive.metadata.references = []
                    # if any item in the references list starts with 10. add the prefix https://doi.org/
                    for i, ref in enumerate(archive.metadata.references):
                        if ref.startswith('10.'):
                            archive.metadata.references[i] = 'https://doi.org/' + ref
                    if self.DOI_number not in archive.metadata.references:
                        archive.metadata.references.append(self.DOI_number)

                else:
                    logger.warning(f'Could not parse DOI number {self.DOI_number}')
            except Exception as e:
                logger.warning(f'Could not parse crossref for {self.DOI_number}')
                logger.warning(str(e))


class HDF5Normalizer(ArchiveSection):
    def normalize(self, archive, logger):
        super().normalize(archive, logger)
        h5_re = re.compile(r'.*\.h5$')

        for quantity_name, quantity_def in self.m_def.all_quantities.items():
            if (quantity_def.type is str or isinstance(quantity_def.type, m_str)) and (
                match := re.match(
                    h5_re,
                    '' if self.get(quantity_name) is None else self.get(quantity_name),
                )
            ):
                h5_filepath = os.path.join(
                    archive.m_context.upload_files.os_path, 'raw', match.group(0)
                )
                with h5py.File(h5_filepath, 'r') as h5_file:
                    self.hdf5_parser(h5_file, logger)

    def hdf5_parser(self, h5_file, logger):
        if logger is None:
            logger = utils.get_logger(__name__)

        mapping = create_custom_mapping(self.m_def, HDF5Annotation, 'hdf5', 'path')  # type: ignore
        for custom_quantities in mapping:
            h5_path = custom_quantities[0]
            quantity_mapper = custom_quantities[1]
            try:
                dataset = h5_file[h5_path]
                quantity_mapper(self, dataset[:])
            except Exception as e:
                logger.warning(
                    f'Could not map the path {h5_path}.'
                    f'Either the path does not exist or the custom quantity cannot hold the content of'
                    f' h5 dataset',
                    exc_info=e,
                )
