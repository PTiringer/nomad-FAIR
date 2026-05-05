export const defaultApp = {
  "label": "Entries",
  "path": "entries",
  "resource": "entries",
  "category": "All",
  "description": "Search entries across all domains",
  "readme": "This page allows you to search **entries** within NOMAD. Entries represent any individual data items that have been uploaded to NOMAD, no matter whether they come from theoretical calculations, experiments, lab notebooks or any other source of data. This allows you to perform cross-domain queries, but if you are interested in a specific subfield, you should see if a specific application exists for it in the explore menu to get more details.",
  "pagination": {
    "order_by": "upload_create_time",
    "order": "desc",
    "page_size": 20
  },
  "columns": [
    {
    "search_quantity": "entry_name",
    "selected": true,
    "title": "Name",
    "align": "left"
    },
    {
    "search_quantity": "results.material.chemical_formula_hill",
    "selected": true,
    "title": "Formula",
    "align": "left"
    },
    {
    "search_quantity": "entry_type",
    "selected": true,
    "align": "left"
    },
    {
    "search_quantity": "upload_create_time",
    "selected": true,
    "title": "Project time",
    "align": "left"
    },
    {
    "search_quantity": "authors",
    "selected": true,
    "align": "left"
    },
    {
    "search_quantity": "upload_name",
    "selected": false,
    "title": "Project name",
    "align": "left"
    },
    {
    "search_quantity": "upload_id",
    "selected": false,
    "title": "Project id",
    "align": "left"
    },
    {
    "search_quantity": "results.method.method_name",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.program_name",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.dft.xc_functional_type",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.precision.apw_cutoff",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.precision.basis_set",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.precision.k_line_density",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.precision.native_tier",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.method.simulation.precision.planewave_cutoff",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.material.structural_type",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.material.symmetry.crystal_system",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.material.symmetry.space_group_symbol",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.material.symmetry.space_group_number",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.eln.lab_ids",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.eln.sections",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.eln.methods",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.eln.tags",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "results.eln.instruments",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "mainfile",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "comment",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "references",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "datasets",
    "selected": false,
    "align": "left"
    },
    {
    "search_quantity": "published",
    "selected": false,
    "title": "Access",
    "align": "left"
    }
  ],
  "rows": {
    "actions": {
    "enabled": true
    },
    "details": {
    "enabled": true
    },
    "selection": {
    "enabled": true
    }
  },
  "menu": {
    "width": 12,
    "show_header": true,
    "title": "Filters",
    "type": "menu",
    "size": "sm",
    "indentation": 0,
    "items": [
    {
      "width": 12,
      "show_header": true,
      "title": "Material",
      "type": "menu",
      "size": "md"
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Elements / Formula",
      "type": "menu",
      "size": "xxl",
      "indentation": 1,
      "items": [
      {
        "type": "periodic_table",
        "search_quantity": "results.material.elements",
        "scale": "linear",
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.chemical_formula_hill",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 6,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.chemical_formula_iupac",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 6,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.chemical_formula_reduced",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 6,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.chemical_formula_anonymous",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 6,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.material.n_elements",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Structure / Symmetry",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.material.structural_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.bravais_lattice",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 2,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.crystal_system",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 2,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.space_group_symbol",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.structure_name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 5,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.strukturbericht_designation",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.point_group",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.hall_symbol",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.symmetry.prototype_aflow_id",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Method",
      "type": "menu",
      "size": "md",
      "items": [
      {
        "search_quantity": "results.method.simulation.program_name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.program_version",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Precision",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.precision.k_line_density",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.precision.native_tier",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.precision.basis_set",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 5,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.precision.planewave_cutoff",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.precision.apw_cutoff",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "DFT",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "DFT": {
          "label": "Search DFT entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "search_quantity": "results.method.simulation.dft.xc_functional_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.dft.xc_functional_names",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.dft.exact_exchange_mixing_factor",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.dft.hubbard_kanamori_model.u_effective",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.dft.core_electron_treatment",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.dft.relativity_method",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "TB",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "TB": {
          "label": "Search TB entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "search_quantity": "results.method.simulation.tb.type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.tb.localization_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "GW",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "GW": {
          "label": "Search GW entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "search_quantity": "results.method.simulation.gw.type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.gw.starting_point_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.gw.basis_set_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "BSE",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "BSE": {
          "label": "Search BSE entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "search_quantity": "results.method.simulation.bse.type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.bse.solver",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.bse.starting_point_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.bse.starting_point_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.bse.basis_set_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.bse.gw_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "DMFT",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "DMFT": {
          "label": "Search DMFT entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "search_quantity": "results.method.simulation.dmft.impurity_solver_type",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 2,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.dmft.inverse_temperature",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.dmft.magnetic_state",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.dmft.u",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.method.simulation.dmft.jh",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.method.simulation.dmft.analytical_continuation",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "EELS",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.method_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "EELS": {
          "label": "Search EELS entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.spectroscopic.spectra.provenance.eels",
        "items": [
        {
          "search_quantity": "results.properties.spectroscopic.spectra.provenance.eels.detector_type",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.spectroscopic.spectra.provenance.eels.resolution",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.spectroscopic.spectra.provenance.eels.min_energy",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.spectroscopic.spectra.provenance.eels.max_energy",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Workflow",
      "type": "menu",
      "size": "md"
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Molecular dynamics",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.method.workflow_name",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "MolecularDynamics": {
          "label": "Search molecular dynamics entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.thermodynamic.trajectory",
        "items": [
        {
          "search_quantity": "results.properties.thermodynamic.trajectory.available_properties",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "options": 4,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "search_quantity": "results.properties.thermodynamic.trajectory.provenance.molecular_dynamics.ensemble_type",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "options": 2,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.thermodynamic.trajectory.provenance.molecular_dynamics.time_step",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Geometry Optimization",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.properties.available_properties",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": false,
        "options": {
        "geometry_optimization": {
          "label": "Search geometry optimization entries"
        }
        },
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": false
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.geometry_optimization",
        "items": [
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.geometry_optimization.final_energy_difference",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.geometry_optimization.final_force_maximum",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.geometry_optimization.final_displacement_maximum",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Properties",
      "type": "menu",
      "size": "md"
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Electronic",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "electronic_properties",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.electronic.band_structure_electronic.band_gap",
        "items": [
        {
          "search_quantity": "results.properties.electronic.band_structure_electronic.band_gap.type",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "options": 2,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.electronic.band_structure_electronic.band_gap.value",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.electronic.band_structure_electronic",
        "items": [
        {
          "search_quantity": "results.properties.electronic.band_structure_electronic.spin_polarized",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        }
        ]
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.electronic.dos_electronic",
        "items": [
        {
          "search_quantity": "results.properties.electronic.dos_electronic.spin_polarized",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Vibrational",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "vibrational_properties",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Mechanical",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "mechanical_properties",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.mechanical.bulk_modulus",
        "items": [
        {
          "search_quantity": "results.properties.mechanical.bulk_modulus.type",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.mechanical.bulk_modulus.value",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.mechanical.shear_modulus",
        "items": [
        {
          "search_quantity": "results.properties.mechanical.shear_modulus.type",
          "type": "terms",
          "scale": "linear",
          "show_input": false,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.mechanical.shear_modulus.value",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.mechanical.energy_volume_curve",
        "items": [
        {
          "search_quantity": "results.properties.mechanical.energy_volume_curve.type",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "options": 5,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Use Cases",
      "type": "menu",
      "size": "md"
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Solar Cells",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.efficiency",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.fill_factor",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.open_circuit_voltage",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.short_circuit_current_density",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.illumination_intensity",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.optoelectronic.solar_cell.device_area",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.device_architecture",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.device_stack",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.absorber",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.absorber_fabrication",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.electron_transport_layer",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.hole_transport_layer",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.substrate",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.properties.optoelectronic.solar_cell.back_contact",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Heterogeneous Catalysis",
      "type": "menu",
      "size": "md",
      "indentation": 1,
      "items": [
      {
        "search_quantity": "results.properties.catalytic.reaction.name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.catalytic.reaction.reactants",
        "items": [
        {
          "search_quantity": "results.properties.catalytic.reaction.reactants.name",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.reaction.reactants.conversion",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.reaction.reactants.mole_fraction_in",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.reaction.reactants.mole_fraction_out",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.catalytic.reaction.products",
        "items": [
        {
          "search_quantity": "results.properties.catalytic.reaction.products.name",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.reaction.products.selectivity",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.reaction.products.mole_fraction_out",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "results.properties.catalytic.reaction.reaction_conditions.temperature",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "width": 12,
        "show_header": true,
        "type": "nested_object",
        "path": "results.properties.catalytic.catalyst",
        "items": [
        {
          "search_quantity": "results.properties.catalytic.catalyst.catalyst_type",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "search_quantity": "results.properties.catalytic.catalyst.preparation_method",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "search_quantity": "results.properties.catalytic.catalyst.catalyst_name",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "search_quantity": "results.properties.catalytic.catalyst.support",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "search_quantity": "results.properties.catalytic.catalyst.characterization_methods",
          "type": "terms",
          "scale": "linear",
          "show_input": true,
          "width": 12,
          "show_header": true,
          "n_columns": 1,
          "sort_static": true,
          "show_statistics": true
        },
        {
          "type": "histogram",
          "show_input": true,
          "x": {
          "search_quantity": "results.properties.catalytic.catalyst.surface_area",
          "scale": "linear"
          },
          "y": {
          "scale": "linear"
          },
          "autorange": false,
          "width": 12,
          "show_header": true,
          "show_statistics": true
        }
        ]
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Author / Origin / Dataset",
      "type": "menu",
      "size": "lg",
      "items": [
      {
        "search_quantity": "authors.name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "type": "histogram",
        "show_input": true,
        "x": {
        "search_quantity": "upload_create_time",
        "scale": "linear"
        },
        "y": {
        "scale": "linear"
        },
        "autorange": false,
        "width": 12,
        "show_header": true,
        "show_statistics": true
      },
      {
        "search_quantity": "external_db",
        "type": "terms",
        "scale": "linear",
        "show_input": false,
        "width": 12,
        "show_header": true,
        "options": 5,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "datasets.dataset_name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "datasets.doi",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Visibility / IDs / Schema",
      "type": "menu",
      "size": "md",
      "items": [
      {
        "width": 12,
        "show_header": true,
        "type": "visibility"
      },
      {
        "search_quantity": "entry_id",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "upload_id",
        "title": "Project id",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "upload_name",
        "title": "Project name",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "results.material.material_id",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "search_quantity": "datasets.dataset_id",
        "type": "terms",
        "scale": "linear",
        "show_input": true,
        "width": 12,
        "show_header": true,
        "options": 0,
        "n_columns": 1,
        "sort_static": true,
        "show_statistics": true
      },
      {
        "width": 12,
        "show_header": true,
        "type": "definitions"
      }
      ]
    },
    {
      "width": 12,
      "show_header": true,
      "title": "Optimade",
      "type": "menu",
      "size": "lg",
      "items": [
      {
        "width": 12,
        "show_header": true,
        "type": "optimade"
      }
      ]
    }
    ]
  },
  "filters": {
    "exclude": [
    "mainfile",
    "entry_name",
    "combine"
    ]
  },
  "search_quantities": {
    "exclude": [
    "mainfile",
    "entry_name",
    "combine"
    ]
  },
  "search_syntaxes": {
    "exclude": [
    "free_text"
    ]
  }
}
