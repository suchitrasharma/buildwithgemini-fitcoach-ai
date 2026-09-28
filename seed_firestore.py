"""Seed script to populate Firestore with sample exercise catalog and workout logs.
Hardcodes project ID as a string to avoid project-number resolution issues on Agent Platform.
"""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-7a8c674b8d70"


def seed():
    print(f"Connecting to Firestore in project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)

    exercises = [
        {
            "exercise_id": "bench-press",
            "name": "Barbell Bench Press",
            "category": "Chest",
            "target_muscles": ["Pectoralis Major", "Triceps", "Anterior Deltoid"],
            "equipment": "Barbell, Flat Bench",
            "difficulty": "Intermediate",
            "instructions": "Lie flat on bench, grip bar with hands slightly wider than shoulder width, lower bar to mid-chest, press up explosively.",
        },
        {
            "exercise_id": "barbell-squat",
            "name": "Barbell Back Squat",
            "category": "Legs",
            "target_muscles": ["Quadriceps", "Gluteus Maximus", "Hamstrings"],
            "equipment": "Barbell, Squat Rack",
            "difficulty": "Intermediate",
            "instructions": "Position bar on upper back, feet shoulder-width apart, lower hips until thighs are parallel to ground, drive through heels to stand.",
        },
        {
            "exercise_id": "deadlift",
            "name": "Conventional Deadlift",
            "category": "Back",
            "target_muscles": ["Erector Spinae", "Hamstrings", "Gluteus Maximus", "Lats"],
            "equipment": "Barbell, Weight Plates",
            "difficulty": "Advanced",
            "instructions": "Stand with mid-foot under bar, hinge at hips to grip bar, keep chest up, extend hips and knees simultaneously to lift.",
        },
        {
            "exercise_id": "pull-ups",
            "name": "Bodyweight Pull-Ups",
            "category": "Back",
            "target_muscles": ["Latissimus Dorsi", "Biceps", "Rhomboids"],
            "equipment": "Pull-Up Bar",
            "difficulty": "Intermediate",
            "instructions": "Grip bar with palms facing away, pull chest up towards bar until chin clears bar, lower under control.",
        },
        {
            "exercise_id": "overhead-press",
            "name": "Standing Overhead Press",
            "category": "Shoulders",
            "target_muscles": ["Anterior Deltoid", "Triceps", "Upper Chest"],
            "equipment": "Barbell",
            "difficulty": "Intermediate",
            "instructions": "Hold bar at collarbone height, brace core, press bar directly overhead until arms are locked out.",
        },
    ]

    print("Seeding 'exercises' collection...")
    for item in exercises:
        doc_ref = db.collection("exercises").document(item["exercise_id"])
        doc_ref.set(item)
        print(f"  ✓ Seeded exercise: {item['name']}")

    workout_logs = [
        {
            "log_id": "log-1",
            "user_id": "default_user",
            "exercise_name": "Barbell Bench Press",
            "sets": 4,
            "reps": 8,
            "weight_lbs": 185.0,
            "date": "2026-09-27",
            "notes": "Felt strong, good bar speed.",
        },
        {
            "log_id": "log-2",
            "user_id": "default_user",
            "exercise_name": "Barbell Back Squat",
            "sets": 3,
            "reps": 5,
            "weight_lbs": 225.0,
            "date": "2026-09-28",
            "notes": "Worked on depth and knee tracking.",
        },
    ]

    print("Seeding 'workout_logs' collection...")
    for item in workout_logs:
        doc_ref = db.collection("workout_logs").document(item["log_id"])
        doc_ref.set(item)
        print(f"  ✓ Seeded workout log: {item['exercise_name']} ({item['weight_lbs']} lbs)")

    print("✅ Seeding complete!")


if __name__ == "__main__":
    seed()
