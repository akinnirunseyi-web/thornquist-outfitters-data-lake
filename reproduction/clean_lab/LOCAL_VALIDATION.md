# Repository runner validation — 23 October 2026 (UTC)

The 20 offline unit checks include a Landing POS catalog definition and count-query check. The earlier version 1.1 runner passed 50 botocore 1.43.118 request-model checks, including Glue queuing parameters, without sending AWS requests. The version 1.2 Landing addition is covered by the current 20 offline checks; it has not been run in AWS. The original fixtures still reconcile to 1,601 lines and 320,570.35 source monetary units. Source hashes are unchanged. Existing account, resource ownership, CTAS, identifier, quality-report, analytics escaping and no-duplicate safeguards remain checked.

New cases cover explicit Glue concurrency rejection followed by a queued run, resuming a definitively rejected request, refusing duplicate submission after an unknown network result, genuine S3 event re-upload of identical Landing bytes, refusing a bad Raw checksum and a bounded event wait that never writes Raw or directly invokes Lambda.

In the version 1.0 AWS rehearsal, actual S3 copies, customer ingestion, Raw crawlers/Athena checks and both sales Glue jobs were successful. The initial event required a manual identical re-upload. The corrected job required a manually queued submission and guarded checkpoint linking after ConcurrentRunsExceededException. The version 1.1 launcher implements retries/queuing for these cases.

The `rehearsal01` AWS pipeline run completed on 23 October and its evidence ZIP was downloaded. The Landing catalog definition and Athena count check are included in this repository runner; the AWS demonstration showed tables across all four zones. Keep the recorded AWS run manifest and presentation recording with the submission.
