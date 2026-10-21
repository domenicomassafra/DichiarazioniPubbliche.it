"""Strict private Capture collection DTO for Studio's nonce-bound JavaScript."""

CAPTURE_ROUTE_BROWSER_JS = r"""
    function safeCollectionCaptures(receipt, request) {
      const scope = receipt?.data;
      const exact = (value, fields) => value && typeof value === 'object'
        && !Array.isArray(value) && Object.keys(value).length === fields.length
        && fields.every(field => Object.hasOwn(value, field));
      if (!exact(receipt, ['contract_version', 'data'])
          || !exact(scope, ['contract_version', 'private_only', 'publication_authority',
            'rights_clearance', 'capture_authorized', 'collection_id', 'content_id',
            'source_id', 'source_exists', 'collection_state', 'rights_status',
            'processing_status', 'captures', 'has_more', 'next_after_id'])
          || receipt.contract_version !== 'studio-local-readonly-api-v1'
          || scope.contract_version !== 'studio-collection-captures-v1'
          || scope.private_only !== true || scope.publication_authority !== false
          || scope.rights_clearance !== false || scope.capture_authorized !== false
          || scope.collection_id !== request.collection_id
          || scope.content_id !== request.content_id
          || !SAFE_REF.test(scope.collection_id) || !SAFE_REF.test(scope.content_id)
          || !SAFE_REF.test(scope.source_id) || scope.source_exists !== true
          || !['ACTIVE', 'PAUSED', 'ARCHIVED'].includes(scope.collection_state)
          || !['UNKNOWN', 'UNRESOLVED', 'EXPIRED', 'CONFLICTING', 'REVOKED',
            'BLOCKED', 'FORBIDDEN', 'LEGAL_HOLD', 'RIGHTS_HOLD', 'TAKEDOWN_HOLD',
            'REMOVED', 'CLEARED'].includes(scope.rights_status)
          || !/^[A-Z][A-Z_]{0,64}$/.test(scope.processing_status)
          || !Number.isSafeInteger(request.limit) || request.limit < 1 || request.limit > 20
          || !Array.isArray(scope.captures) || scope.captures.length > request.limit
          || typeof scope.has_more !== 'boolean'
          || (scope.has_more ? scope.captures.length !== request.limit
            || scope.next_after_id !== scope.captures.at(-1)?.id
            : scope.next_after_id !== null)) return null;
      const rowFields = ['id', 'content_sha256', 'observed_at', 'status', 'archive_status'];
      let previous = request.after_id || '';
      const captures = [];
      for (const row of scope.captures) {
        if (!exact(row, rowFields) || !SAFE_REF.test(row.id) || row.id <= previous
            || !SAFE_SHA256.test(row.content_sha256)
            || typeof row.observed_at !== 'string' || row.observed_at.length > 40
            || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(row.observed_at)
            || !Number.isFinite(Date.parse(row.observed_at))
            || !['CAPTURED', 'QUARANTINED', 'PURGE_PENDING', 'PURGED_BODY'].includes(row.status)
            || !['NOT_REQUESTED', 'REQUESTED', 'PENDING', 'SUCCEEDED', 'FAILED']
              .includes(row.archive_status)) return null;
        previous = row.id;
        captures.push({id: row.id, content_sha256: row.content_sha256,
          observed_at: row.observed_at, status: row.status, archive_status: row.archive_status});
      }
      return {collection_id: scope.collection_id, content_id: scope.content_id,
        source_id: scope.source_id, rights_status: scope.rights_status,
        captures, has_more: scope.has_more, next_after_id: scope.next_after_id};
    }
"""
