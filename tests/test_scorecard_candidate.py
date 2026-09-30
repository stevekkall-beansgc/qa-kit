"""Contract checks for the disabled scorecard proposal, not runtime tests."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_unique_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


class ScorecardCandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_unique_json(ROOT / "scorecards" / "policy.candidate.json")
        cls.fixtures = load_unique_json(ROOT / "scorecards" / "acceptance-cases.json")

    def test_health_boundaries_match_policy_and_remain_specifications(self):
        policy = self.policy
        fixtures = self.fixtures
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["policy_version"], fixtures["policy_version"])
        self.assertEqual(fixtures["status"], "specification-fixtures-not-executed-tests")
        health = policy["health"]
        weights = [category["weight"] for category in health["categories"]]
        self.assertEqual(sum(weights), health["scale"])
        self.assertEqual(health["formula"], "sum(weight * rating / 4)")
        self.assertEqual(health["coverage_formula"],
                         "sum(weights of categories with complete current required evidence)")
        self.assertEqual(health["status_precedence"], [
            "confirmed_blocker_red", "missing_required_evidence_unknown",
            "numeric_and_floor_rules",
        ])
        cases = fixtures["health_cases"]
        self.assertEqual(len(cases), 9)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))

        for case in cases:
            with self.subTest(case=case["id"]):
                ratings = case["ratings"]
                complete = case["complete"]
                self.assertEqual(len(ratings), len(weights))
                self.assertEqual(len(complete), len(weights))
                self.assertTrue(all(type(flag) is bool for flag in complete))
                self.assertTrue(all(rating is None or
                                    type(rating) is int and 0 <= rating <= 4
                                    for rating in ratings))
                self.assertTrue(all((rating is None) == (not flag)
                                    for rating, flag in zip(ratings, complete)))
                points = sum(weight * (rating or 0) / 4
                             for weight, rating in zip(weights, ratings))
                coverage = sum(weight for weight, flag in zip(weights, complete)
                               if flag)
                bands = health["bands"]
                if case["blockers"]:
                    status = "red"
                elif not all(complete):
                    status = "unknown"
                elif points >= bands["green_min"] and all(
                        rating >= bands["green_category_floor"] for rating in ratings):
                    status = "green"
                elif points >= bands["amber_min"]:
                    status = "amber"
                else:
                    status = "red"
                self.assertEqual(case["expected"], {
                    "points": points, "coverage": coverage, "status": status,
                })

    def test_history_replay_and_no_spend_gates_remain_explicit(self):
        acceptance_cases = self.fixtures["acceptance_requirements"]
        names = [case["case"] for case in acceptance_cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue({"replayed_assessment", "later_delivery_retry",
                         "conflicting_replay", "offline_history_recovery",
                         "budget_unverified", "data_safety"} <= set(names))
        self.assertTrue(all(case["expected"] for case in acceptance_cases))
        history = self.policy["history"]
        required = set(history["required_fields"])
        self.assertIn("source_observation_id", required)
        self.assertTrue(set(history["assessment_id_inputs"]) <= required)
        self.assertEqual(history["identity_canonicalization"], "RFC8785_JSON_SHA256")
        self.assertEqual(set(history["content_hash_excludes"]),
                         {"content_sha256", "ingested_at"})
        self.assertEqual(history["ingested_at_assignment"],
                         "first_accepted_create_only")
        self.assertTrue(history["source_observation_id_reused_on_retry"])
        self.assertTrue(history["correction_requires_new_source_observation_id"])
        self.assertTrue(history["append_only"])
        self.assertFalse(history["automatic_deletion"])

        storage = self.policy["storage"]
        rollout = self.policy["rollout"]
        self.assertFalse(storage["provisioned"])
        self.assertFalse(storage["enabled"])
        self.assertFalse(storage["hosted_restore_verified"])
        self.assertFalse(storage["managed_backup_restore_pitr_ttl_allowed_without_billing"])
        self.assertEqual(storage["public_config_personal_hiring_assessments"],
                         "forbidden")
        self.assertEqual(storage["public_config_private_local_paths"], "forbidden")
        for field in ("cloud_summary_personal_hiring_assessments",
                      "cloud_summary_private_local_paths"):
            self.assertEqual(storage[field],
                             "reject_without_separate_specific_data_disclosure_approval")
        self.assertEqual(storage["recovery_mode"],
                         "bounded_application_export_and_offline_restore")
        self.assertTrue({
            "no_new_spend_control_review",
            "approved_private_export_and_offline_restore_verification",
            "export_reads_within_free_allowance",
            "explicit_data_disclosure_approval",
        } <= set(storage["activation_requires"]))
        for field in ("collection_enabled", "scheduling_enabled",
                      "cloud_writes_enabled", "gate_enforcement_enabled"):
            self.assertFalse(rollout[field])


if __name__ == "__main__":
    unittest.main()
