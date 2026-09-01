"""recipe_manager 의 Job·Recipe·RecipeManager 직렬화/로드/저장을 검증한다."""
import pytest
import os
import yaml
from tm_task_manager.recipe_manager import Job, Recipe, RecipeManager


class TestJob:
    def test_job_init_with_defaults(self):
        job = Job(job_id=1, job_type='go_home')

        assert job.id == 1
        assert job.type == 'go_home'
        assert job.name == 'go_home'
        assert job.params == {}
        assert job.caption == ''

    def test_job_init_with_all_params(self):
        params = {'velocity': 50.0, 'X': 100.0}
        job = Job(
            job_id=2,
            job_type='move_to_point',
            name='Test Move',
            params=params,
            caption='Custom Caption'
        )

        assert job.id == 2
        assert job.type == 'move_to_point'
        assert job.name == 'Test Move'
        assert job.params == params
        assert job.caption == 'Custom Caption'

    def test_job_to_dict(self):
        job = Job(job_id=1, job_type='go_home', name='Go Home')
        result = job.to_dict()

        assert result['id'] == 1
        assert result['type'] == 'go_home'
        assert result['name'] == 'Go Home'
        assert 'caption' not in result
        assert 'params' not in result

    def test_job_to_dict_with_caption(self):
        job = Job(job_id=1, job_type='go_home', caption='My Caption')
        result = job.to_dict()

        assert result['caption'] == 'My Caption'

    def test_job_to_dict_without_empty_params(self):
        job = Job(job_id=1, job_type='go_home', params={})
        result = job.to_dict()

        assert 'params' not in result

    def test_job_from_dict(self):
        data = {
            'id': 3,
            'type': 'wait',
            'name': 'Wait Job',
            'params': {'duration': 1000},
            'caption': 'Test Caption'
        }
        job = Job.from_dict(data)

        assert job.id == 3
        assert job.type == 'wait'
        assert job.name == 'Wait Job'
        assert job.params == {'duration': 1000}
        assert job.caption == 'Test Caption'

    def test_job_from_dict_with_missing_keys(self):
        data = {}
        job = Job.from_dict(data)

        assert job.id == 0
        assert job.type == 'unknown'
        assert job.name == 'unknown'
        assert job.params == {}
        assert job.caption == ''


class TestRecipe:
    def test_recipe_init(self):
        recipe = Recipe(name='Test Recipe', description='Test Description')

        assert recipe.name == 'Test Recipe'
        assert recipe.description == 'Test Description'
        assert recipe.version == '1.0'
        assert recipe.jobs == []
        assert recipe.file_path is None
        assert recipe.created is not None
        assert recipe.modified == recipe.created

    def test_recipe_add_job(self):
        recipe = Recipe()
        job1 = Job(job_id=0, job_type='go_home')
        job2 = Job(job_id=0, job_type='wait')

        recipe.add_job(job1)
        recipe.add_job(job2)

        assert len(recipe.jobs) == 2
        assert recipe.jobs[0].id == 1
        assert recipe.jobs[1].id == 2

    def test_recipe_remove_job(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        job2 = Job(job_id=2, job_type='wait')
        job3 = Job(job_id=3, job_type='gripper_open')

        recipe.add_job(job1)
        recipe.add_job(job2)
        recipe.add_job(job3)

        recipe.remove_job(1)

        assert len(recipe.jobs) == 2
        assert recipe.jobs[0].type == 'go_home'
        assert recipe.jobs[1].type == 'gripper_open'
        assert recipe.jobs[0].id == 1
        assert recipe.jobs[1].id == 2

    def test_recipe_remove_job_invalid_index(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        recipe.add_job(job1)

        recipe.remove_job(10)

        assert len(recipe.jobs) == 1

    def test_recipe_move_job_up(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        job2 = Job(job_id=2, job_type='wait')

        recipe.add_job(job1)
        recipe.add_job(job2)

        result = recipe.move_job_up(1)

        assert result is True
        assert recipe.jobs[0].type == 'wait'
        assert recipe.jobs[1].type == 'go_home'
        assert recipe.jobs[0].id == 1
        assert recipe.jobs[1].id == 2

    def test_recipe_move_job_up_first_job(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        recipe.add_job(job1)

        result = recipe.move_job_up(0)

        assert result is False
        assert recipe.jobs[0].type == 'go_home'

    def test_recipe_move_job_down(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        job2 = Job(job_id=2, job_type='wait')

        recipe.add_job(job1)
        recipe.add_job(job2)

        result = recipe.move_job_down(0)

        assert result is True
        assert recipe.jobs[0].type == 'wait'
        assert recipe.jobs[1].type == 'go_home'
        assert recipe.jobs[0].id == 1
        assert recipe.jobs[1].id == 2

    def test_recipe_move_job_down_last_job(self):
        recipe = Recipe()
        job1 = Job(job_id=1, job_type='go_home')
        recipe.add_job(job1)

        result = recipe.move_job_down(0)

        assert result is False
        assert recipe.jobs[0].type == 'go_home'

    def test_recipe_to_dict(self):
        recipe = Recipe(name='Test Recipe', description='Test Desc')
        job = Job(job_id=1, job_type='go_home')
        recipe.add_job(job)

        result = recipe.to_dict()

        assert result['name'] == 'Test Recipe'
        assert result['description'] == 'Test Desc'
        assert result['version'] == '1.0'
        assert 'created' in result
        assert 'modified' in result
        assert len(result['jobs']) == 1
        assert result['jobs'][0]['type'] == 'go_home'

    def test_recipe_from_dict(self):
        data = {
            'name': 'Loaded Recipe',
            'description': 'Loaded Desc',
            'version': '1.0',
            'created': '2025-01-01',
            'modified': '2025-01-02',
            'jobs': [
                {'id': 1, 'type': 'go_home', 'name': 'Go Home', 'params': {}},
                {'id': 2, 'type': 'wait', 'name': 'Wait', 'params': {'duration': 1000}}
            ]
        }
        recipe = Recipe.from_dict(data)

        assert recipe.name == 'Loaded Recipe'
        assert recipe.description == 'Loaded Desc'
        assert recipe.version == '1.0'
        assert recipe.created == '2025-01-01'
        assert recipe.modified == '2025-01-02'
        assert len(recipe.jobs) == 2
        assert recipe.jobs[0].type == 'go_home'
        assert recipe.jobs[1].type == 'wait'


class TestRecipeManager:
    def test_manager_init(self):
        manager = RecipeManager(recipe_dir='/tmp/test_recipes')

        assert manager.recipe_dir == '/tmp/test_recipes'
        assert manager.current_recipe is None
        assert manager.max_recent_files == 4
        assert isinstance(manager.recent_files, list)

    def test_manager_new_recipe(self):
        manager = RecipeManager(recipe_dir='/tmp/test_recipes')
        recipe = manager.new_recipe(name='New Recipe', description='New Desc')

        assert recipe.name == 'New Recipe'
        assert recipe.description == 'New Desc'
        assert manager.current_recipe == recipe

    def test_manager_save_recipe(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))
        recipe = manager.new_recipe(name='Save Test')
        job = Job(job_id=1, job_type='go_home')
        recipe.add_job(job)

        file_path = manager.save_recipe(recipe, 'test_save.yaml')

        assert os.path.exists(file_path)
        assert file_path.endswith('test_save.yaml')

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'Save Test' in content
            assert 'go_home' in content

    def test_manager_load_recipe(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))

        recipe = manager.new_recipe(name='Load Test')
        job = Job(job_id=1, job_type='wait', params={'duration': 2000})
        recipe.add_job(job)
        file_path = manager.save_recipe(recipe, 'test_load.yaml')

        loaded = manager.load_recipe(file_path)

        assert loaded.name == 'Load Test'
        assert len(loaded.jobs) == 1
        assert loaded.jobs[0].type == 'wait'
        assert loaded.jobs[0].params['duration'] == 2000
        assert manager.current_recipe == loaded

    def test_manager_save_and_load_roundtrip(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))

        recipe = manager.new_recipe(name='Roundtrip Test', description='Test Desc')
        job1 = Job(job_id=1, job_type='go_home', params={'velocity': 30.0})
        job2 = Job(job_id=2, job_type='wait', params={'duration': 1500}, caption='Wait Job')
        recipe.add_job(job1)
        recipe.add_job(job2)

        file_path = manager.save_recipe(recipe, 'roundtrip.yaml')

        loaded = manager.load_recipe(file_path)

        assert loaded.name == recipe.name
        assert loaded.description == recipe.description
        assert len(loaded.jobs) == len(recipe.jobs)
        assert loaded.jobs[0].params['velocity'] == 30.0
        assert loaded.jobs[1].params['duration'] == 1500
        assert loaded.jobs[1].caption == 'Wait Job'

    def test_manager_load_nonexistent_file(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            manager.load_recipe('nonexistent.yaml')

    def test_manager_list_recipes(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))

        recipe1 = manager.new_recipe(name='Recipe 1', description='First')
        manager.save_recipe(recipe1, 'recipe1.yaml')

        recipe2 = manager.new_recipe(name='Recipe 2', description='Second')
        manager.save_recipe(recipe2, 'recipe2.yaml')

        recipes = manager.list_recipes()

        assert len(recipes) == 2
        names = [r['name'] for r in recipes]
        assert 'Recipe 1' in names
        assert 'Recipe 2' in names

    def test_manager_create_job(self):
        manager = RecipeManager(recipe_dir='/tmp/test_recipes')
        manager.new_recipe()

        job = manager.create_job('go_home')
        assert job.type == 'go_home'
        assert job.name == 'HOME 이동'
        assert 'velocity' in job.params

        job2 = manager.create_job('wait')
        assert job2.type == 'wait'
        assert job2.params['duration'] == 1000

    def test_manager_create_job_invalid_type(self):
        manager = RecipeManager(recipe_dir='/tmp/test_recipes')

        with pytest.raises(ValueError, match="알 수 없는 Job 타입"):
            manager.create_job('invalid_job_type')

    def test_manager_get_job_types_by_category(self):
        manager = RecipeManager(recipe_dir='/tmp/test_recipes')

        categories = manager.get_job_types_by_category()

        assert 'Motion' in categories
        assert 'Vision' in categories
        assert 'Control' in categories
        assert 'Gripper' in categories

        assert 'go_home' in categories['Motion']
        assert 'wait' in categories['Control']
        assert 'scan_ar_tag' in categories['Vision']
        assert 'gripper_open' in categories['Gripper']

    def test_manager_recent_files(self, tmp_path):
        manager = RecipeManager(recipe_dir=str(tmp_path))

        file1 = str(tmp_path / 'file1.yaml')
        file2 = str(tmp_path / 'file2.yaml')
        file3 = str(tmp_path / 'file3.yaml')
        file4 = str(tmp_path / 'file4.yaml')
        file5 = str(tmp_path / 'file5.yaml')

        for f in [file1, file2, file3, file4, file5]:
            with open(f, 'w') as fp:
                fp.write('dummy')

        manager.add_to_recent_files(file1)
        manager.add_to_recent_files(file2)
        manager.add_to_recent_files(file3)

        recent = manager.get_recent_files()
        assert len(recent) == 3
        assert recent[0] == file3
        assert recent[1] == file2
        assert recent[2] == file1

        manager.add_to_recent_files(file1)
        recent = manager.get_recent_files()
        assert recent[0] == file1
        assert len(recent) == 3

        manager.add_to_recent_files(file4)
        manager.add_to_recent_files(file5)
        recent = manager.get_recent_files()
        assert len(recent) == 4
        assert recent[0] == file5
        assert recent == [file5, file4, file1, file3]
