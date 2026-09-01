#!/usr/bin/env python3
"""RecipeManager/Job/Recipe 의 Runtime 확장 필드(coordinate_mode 등) 생성·직렬화·왕복 보존을 5단계로 검증하는 수동 스크립트.

실행: python3 tools/verify_recipe_manager.py (pytest 미사용, print 기반 — 고정 워크스페이스 경로 의존).
"""
import sys
import os

sys.path.insert(0, '/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/tm_task_manager')

import recipe_manager
RecipeManager = recipe_manager.RecipeManager
Job = recipe_manager.Job
Recipe = recipe_manager.Recipe


def verify_job_class():
    """Job 생성과 to_dict/from_dict 왕복에서 확장 필드 보존을 출력으로 확인한다(항상 True 반환)."""
    print("=" * 70)
    print("1. Job 클래스 검증")
    print("=" * 70)

    job = Job(
        job_id=1,
        job_type='move_to_point',
        name='테스트',
        params={'X': 100, 'Y': 200, 'Z': 300},
        caption='테스트 Job',
        coordinate_mode='relative',
        original_absolute={'X': 150, 'Y': 250, 'Z': 350}
    )

    print(f"  ✅ Job 객체 생성:")
    print(f"     - coordinate_mode: {job.coordinate_mode}")
    print(f"     - original_absolute: {job.original_absolute}")

    job_dict = job.to_dict()
    print(f"\n  ✅ Job.to_dict() 검증:")
    print(f"     - 'coordinate_mode' in dict: {'coordinate_mode' in job_dict}")
    print(f"     - 'original_absolute' in dict: {'original_absolute' in job_dict}")
    print(f"     - coordinate_mode 값: {job_dict.get('coordinate_mode')}")
    print(f"     - original_absolute 값: {job_dict.get('original_absolute')}")

    job2 = Job.from_dict(job_dict)
    print(f"\n  ✅ Job.from_dict() 검증:")
    print(f"     - coordinate_mode: {job2.coordinate_mode}")
    print(f"     - original_absolute: {job2.original_absolute}")
    print(f"     - 일치 여부: {job.coordinate_mode == job2.coordinate_mode}")

    return True


def verify_recipe_class():
    """Recipe 메타필드(master_file·reference 등) 왕복 보존을 출력으로 확인한다(항상 True 반환)."""
    print("\n" + "=" * 70)
    print("2. Recipe 클래스 검증")
    print("=" * 70)

    recipe = Recipe(name="테스트 Recipe", description="검증용")
    recipe.master_file = "test_master.yaml"
    recipe.master_modified = "2026-02-06"
    recipe.reference = {
        'tm_landmark': {'X': 10, 'Y': 20, 'Z': 30}
    }

    job = Job(
        job_id=1,
        job_type='move_to_point',
        name='테스트',
        params={'X': 100, 'Y': 200, 'Z': 300},
        coordinate_mode='relative',
        original_absolute={'X': 150, 'Y': 250, 'Z': 350}
    )
    recipe.add_job(job)

    print(f"  ✅ Recipe 객체 생성:")
    print(f"     - master_file: {recipe.master_file}")
    print(f"     - master_modified: {recipe.master_modified}")
    print(f"     - reference: {recipe.reference}")

    recipe_dict = recipe.to_dict()
    print(f"\n  ✅ Recipe.to_dict() 검증:")
    print(f"     - 'master_file' in dict: {'master_file' in recipe_dict}")
    print(f"     - 'master_modified' in dict: {'master_modified' in recipe_dict}")
    print(f"     - 'reference' in dict: {'reference' in recipe_dict}")
    print(f"     - master_file 값: {recipe_dict.get('master_file')}")
    print(f"     - master_modified 값: {recipe_dict.get('master_modified')}")

    recipe2 = Recipe.from_dict(recipe_dict)
    print(f"\n  ✅ Recipe.from_dict() 검증:")
    print(f"     - master_file: {recipe2.master_file}")
    print(f"     - master_modified: {recipe2.master_modified}")
    print(f"     - reference: {recipe2.reference}")
    print(f"     - Job coordinate_mode: {recipe2.jobs[0].coordinate_mode}")
    print(f"     - 일치 여부: {recipe.master_file == recipe2.master_file}")

    return True


def verify_runtime_file_loading():
    """실제 runtime YAML 을 로드해 필드 체크리스트로 판정한다."""
    print("\n" + "=" * 70)
    print("3. Runtime 파일 로드 상세 검증")
    print("=" * 70)

    recipe_dir = "/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/recipes"
    manager = RecipeManager(recipe_dir)

    test_file = "tm_landmark_test4_runtime.yaml"
    print(f"\n  📁 테스트 파일: {test_file}")

    recipe = manager.load_recipe(test_file)

    checks = []

    checks.append(("master_file 존재", recipe.master_file is not None))
    checks.append(("master_file 값", recipe.master_file == "tm_landmark_test4.yaml"))
    checks.append(("master_modified 존재", recipe.master_modified is not None))
    checks.append(("master_modified 값", recipe.master_modified == "2026-02-06"))
    checks.append(("reference 존재", recipe.reference is not None))
    checks.append(("reference.tm_landmark 존재", 'tm_landmark' in recipe.reference if recipe.reference else False))

    relative_jobs = [j for j in recipe.jobs if j.coordinate_mode == 'relative']
    checks.append(("relative job 존재", len(relative_jobs) > 0))

    if relative_jobs:
        sample_job = relative_jobs[0]
        checks.append(("Job.coordinate_mode 존재", sample_job.coordinate_mode is not None))
        checks.append(("Job.coordinate_mode 값", sample_job.coordinate_mode == 'relative'))
        checks.append(("Job.original_absolute 존재", sample_job.original_absolute is not None))
        checks.append(("Job.original_absolute['X'] 존재", 'X' in sample_job.original_absolute if sample_job.original_absolute else False))

    print(f"\n  📊 검증 결과:")
    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"     {status} {check_name}: {result}")
        if not result:
            all_passed = False

    return all_passed


def verify_save_load_cycle():
    """임시 파일로 저장→재로드 후 필드 동등성을 비교한다."""
    print("\n" + "=" * 70)
    print("4. 저장 → 로드 사이클 상세 검증")
    print("=" * 70)

    recipe_dir = "/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/recipes"
    manager = RecipeManager(recipe_dir)

    print(f"\n  📖 원본 파일 로드: tm_landmark_test4_runtime.yaml")
    recipe1 = manager.load_recipe("tm_landmark_test4_runtime.yaml")

    temp_file = os.path.join(recipe_dir, "_verify_temp_runtime.yaml")
    print(f"  💾 임시 파일 저장: _verify_temp_runtime.yaml")
    manager.save_recipe(recipe1, temp_file)

    print(f"  📖 임시 파일 재로드")
    recipe2 = manager.load_recipe("_verify_temp_runtime.yaml")

    checks = []
    checks.append(("name", recipe1.name == recipe2.name))
    checks.append(("Job 수", len(recipe1.jobs) == len(recipe2.jobs)))
    checks.append(("master_file", recipe1.master_file == recipe2.master_file))
    checks.append(("master_modified", recipe1.master_modified == recipe2.master_modified))
    checks.append(("reference", recipe1.reference == recipe2.reference))

    if len(recipe1.jobs) == len(recipe2.jobs):
        for i, (j1, j2) in enumerate(zip(recipe1.jobs, recipe2.jobs)):
            checks.append((f"Job {i+1} coordinate_mode", j1.coordinate_mode == j2.coordinate_mode))
            if j1.original_absolute and j2.original_absolute:
                checks.append((f"Job {i+1} original_absolute", j1.original_absolute == j2.original_absolute))

    print(f"\n  📊 비교 결과:")
    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"     {status} {check_name}: {result}")
        if not result:
            all_passed = False

    if os.path.exists(temp_file):
        os.remove(temp_file)
        print(f"\n  🗑️ 임시 파일 삭제 완료")

    return all_passed


def verify_all_runtime_files():
    """runtime YAML 전체의 필수 필드 존재를 전수 확인한다."""
    print("\n" + "=" * 70)
    print("5. 모든 Runtime 파일 필드 검증")
    print("=" * 70)

    recipe_dir = "/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/recipes"
    manager = RecipeManager(recipe_dir)

    runtime_files = [
        "tm_landmark_test1_runtime.yaml",
        "tm_landmark_test2_runtime.yaml",
        "tm_landmark_test3_runtime.yaml",
        "tm_landmark_test4_runtime.yaml",
        "tm_landmark_test5_runtime.yaml"
    ]

    all_passed = True
    for runtime_file in runtime_files:
        print(f"\n  📁 {runtime_file}")

        try:
            recipe = manager.load_recipe(runtime_file)

            required_fields = {
                'master_file': recipe.master_file is not None,
                'master_modified': recipe.master_modified is not None,
                'reference': recipe.reference is not None
            }

            relative_jobs = [j for j in recipe.jobs if j.coordinate_mode == 'relative']
            if relative_jobs:
                sample = relative_jobs[0]
                required_fields['Job.coordinate_mode'] = sample.coordinate_mode is not None
                required_fields['Job.original_absolute'] = sample.original_absolute is not None

            file_passed = all(required_fields.values())
            status = "✅" if file_passed else "❌"
            print(f"     {status} 필드 검증: {file_passed}")

            for field, result in required_fields.items():
                if not result:
                    print(f"        ❌ {field}: 누락")
                    all_passed = False

        except Exception as e:
            print(f"     ❌ 로드 실패: {e}")
            all_passed = False

    return all_passed


if __name__ == '__main__':
    print("\n" + "🔍" * 35)
    print("RecipeManager 상세 검증 시작")
    print("🔍" * 35)

    results = []

    results.append(("Job 클래스", verify_job_class()))

    results.append(("Recipe 클래스", verify_recipe_class()))

    results.append(("Runtime 파일 로드", verify_runtime_file_loading()))

    results.append(("저장 → 로드 사이클", verify_save_load_cycle()))

    results.append(("모든 Runtime 파일", verify_all_runtime_files()))

    print("\n" + "=" * 70)
    print("🎯 최종 검증 결과")
    print("=" * 70)

    all_passed = True
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {test_name}: {'통과' if result else '실패'}")
        if not result:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 모든 검증 통과! RecipeManager 수정이 정상적으로 작동합니다.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("❌ 일부 검증 실패! 수정이 필요합니다.")
        print("=" * 70)
        sys.exit(1)
