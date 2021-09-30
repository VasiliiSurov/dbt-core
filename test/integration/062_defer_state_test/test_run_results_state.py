from test.integration.base import DBTIntegrationTest, use_profile
import os
import random
import shutil
import string

import pytest

from dbt.exceptions import CompilationException

########

# Sung's test cases below

########

class TestRunResultsState(DBTIntegrationTest):
    @property
    def schema(self):
        return "run_results_state_062"

    @property
    def models(self):
        return "models"

    @property
    def project_config(self):
        return {
            'config-version': 2,
            'macro-paths': ['macros'],
            'seeds': {
                'test': {
                    'quote_columns': True,
                }
            }
        }

    def _symlink_test_folders(self):
        # dbt's normal symlink behavior breaks this test. Copy the files
        # so we can freely modify them.
        for entry in os.listdir(self.test_original_source_path):
            src = os.path.join(self.test_original_source_path, entry)
            tst = os.path.join(self.test_root_dir, entry)
            if entry in {'models', 'data', 'macros'}:
                shutil.copytree(src, tst)
            elif os.path.isdir(entry) or entry.endswith('.sql'):
                os.symlink(src, tst)

    def copy_state(self):
        assert not os.path.exists('state')
        os.makedirs('state')
        shutil.copyfile('target/manifest.json', 'state/manifest.json')
        shutil.copyfile('target/run_results.json', 'state/run_results.json')

    #TODO: should this run 'build' because each of these steps may overwrite the previous command's state?
    # TODO: should we remove this setup altogether?
    def setUp(self):
        super().setUp()
        # self.run_dbt(['seed'])
        # self.run_dbt(['run'])
        # self.run_dbt(['test'])
        # self.copy_state()

    # TODO: add a seed file that results in ERROR, then open it up to fix it, then run the seed command with result:error flag
    # TODO: follow the same pattern for the other states
    @use_profile('postgres')
    def test_postgres_seed_run_results_state(self):
        self.run_dbt(['seed'])
        self.copy_state()
        results = self.run_dbt(['ls', '--resource-type', 'seed', '--select', 'result:success', '--state', './state'], expect_pass=True)
        assert len(results) == 1

        results = self.run_dbt(['ls', '--resource-type', 'seed', '--select', 'result:success', '--state', './state'])
        assert len(results) == 1
        assert results[0] == 'test.seed'

        results = self.run_dbt(['ls', '--select', 'result:success', '--state', './state'])
        assert len(results) == 1
        assert results[0] == 'test.seed'

        # TODO: this is to introduce errors to the seed
        # TODO: it exits the test once the seed errors out, need to make sure the rest of the test code is run
        # with open('data/seed.csv') as fp:
        #     fp.readline()
        #     newline = fp.newlines
        # with open('data/seed.csv', 'a') as fp:
        #     fp.write(f'\"\'\'3,carl{newline}')

        # self.run_dbt(['seed'], expect_pass=False)
        # self.copy_state()


    @use_profile('postgres')
    def test_postgres_changed_seed_config(self):
        results = self.run_dbt(['ls', '--resource-type', 'seed', '--select', 'state:modified', '--state', './state'], expect_pass=True)
        assert len(results) == 0

        self.use_default_project({'seeds': {'test': {'quote_columns': False}}})

        # quoting change -> seed changed
        results = self.run_dbt(['ls', '--resource-type', 'seed', '--select', 'state:modified', '--state', './state'])
        assert len(results) == 1
        assert results[0] == 'test.seed'

    @use_profile('postgres')
    def test_postgres_unrendered_config_same(self):
        results = self.run_dbt(['ls', '--resource-type', 'model', '--select', 'state:modified', '--state', './state'], expect_pass=True)
        assert len(results) == 0

        # although this is the default value, dbt will recognize it as a change
        # for previously-unconfigured models, because it's been explicitly set
        self.use_default_project({'models': {'test': {'materialized': 'view'}}})
        results = self.run_dbt(['ls', '--resource-type', 'model', '--select', 'state:modified', '--state', './state'])
        assert len(results) == 1
        assert results[0] == 'test.view_model'

    @use_profile('postgres')
    def test_postgres_changed_model_contents(self):
        results = self.run_dbt(['run', '--models', 'state:modified', '--state', './state'])
        assert len(results) == 0

        with open('models/table_model.sql') as fp:
            fp.readline()
            newline = fp.newlines

        with open('models/table_model.sql', 'w') as fp:
            fp.write("{{ config(materialized='table') }}")
            fp.write(newline)
            fp.write("select * from {{ ref('seed') }}")
            fp.write(newline)

        results = self.run_dbt(['run', '--models', 'state:modified', '--state', './state'])
        assert len(results) == 1
        assert results[0].node.name == 'table_model'


    @use_profile('postgres')
    def test_postgres_changed_exposure(self):
        with open('models/exposures.yml', 'a') as fp:
            fp.write('      name: John Doe\n')

        results, stdout = self.run_dbt_and_capture(['run', '--models', '+state:modified', '--state', './state'])
        assert len(results) == 1
        assert results[0].node.name == 'view_model'

# TODO: add test suite for build command scenarios, can resuse a lot of the content in dbt run test cases

########

# Matt's test cases below

########