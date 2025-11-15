#!/usr/bin/env bash
# Truncate (empty) a DynamoDB table without deleting it
# Usage: ./truncate-dynamodb.sh MyTableName id

set -euo pipefail

TABLE_NAME=${1:-}
KEY_NAME=${2:-}

if [[ -z "$TABLE_NAME" || -z "$KEY_NAME" ]]; then
  echo "Usage: $0 <table-name> <primary-key-name>"
  exit 1
fi

echo "🧹 Truncating DynamoDB table: $TABLE_NAME"
echo "🔑 Using primary key: $KEY_NAME"
echo

LAST_EVALUATED_KEY=""

while :; do
  echo "🔍 Scanning for items..."
  # Scan the table (with pagination)
  SCAN_OUTPUT=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --attributes-to-get "$KEY_NAME" \
    --output json \
    ${LAST_EVALUATED_KEY:+--exclusive-start-key "$LAST_EVALUATED_KEY"})

  ITEM_COUNT=$(echo "$SCAN_OUTPUT" | jq '.Items | length')
  echo "Found $ITEM_COUNT items in this batch."

  if (( ITEM_COUNT == 0 )); then
    echo "✅ No more items to delete. Done!"
    break
  fi

  # Create batch delete payload (max 25 items per batch)
  echo "$SCAN_OUTPUT" | jq -c --arg TABLE "$TABLE_NAME" '
    .Items | map({DeleteRequest: {Key: .}}) 
    | . as $items
    | reduce range(0; length; 25) as $i (
        [];
        . + [{($TABLE): ($items[$i:($i+25)])}]
      )
  ' | while read -r batch; do
      echo "🗑️  Deleting up to 25 items..."
      aws dynamodb batch-write-item --request-items "$batch" >/dev/null
    done

  # Check for pagination
  LAST_EVALUATED_KEY=$(echo "$SCAN_OUTPUT" | jq -c '.LastEvaluatedKey')
  if [[ "$LAST_EVALUATED_KEY" == "null" ]]; then
#!/usr/bin/env bash
# Truncate (empty) a DynamoDB table without deleting it
# Usage: ./truncate-dynamodb.sh MyTableName id

set -euo pipefail

TABLE_NAME=${1:-}
KEY_NAME=${2:-}

if [[ -z "$TABLE_NAME" || -z "$KEY_NAME" ]]; then
  echo "Usage: $0 <table-name> <primary-key-name>"
  exit 1
fi

echo "🧹 Truncating DynamoDB table: $TABLE_NAME"
echo "🔑 Using primary key: $KEY_NAME"
echo

LAST_EVALUATED_KEY=""

while :; do
  echo "🔍 Scanning for items..."
  # Scan the table (with pagination)
  SCAN_OUTPUT=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --attributes-to-get "$KEY_NAME" \
    --output json \
    ${LAST_EVALUATED_KEY:+--exclusive-start-key "$LAST_EVALUATED_KEY"})

  ITEM_COUNT=$(echo "$SCAN_OUTPUT" | jq '.Items | length')
  echo "Found $ITEM_COUNT items in this batch."

  if (( ITEM_COUNT == 0 )); then
    echo "✅ No more items to delete. Done!"
    break
  fi

  # Create batch delete payload (max 25 items per batch)
  echo "$SCAN_OUTPUT" | jq -c --arg TABLE "$TABLE_NAME" '
    .Items | map({DeleteRequest: {Key: .}}) 
    | . as $items
    | reduce range(0; length; 25) as $i (
        [];
        . + [{($TABLE): ($items[$i:($i+25)])}]
      )
  ' | while read -r batch; do
      echo "🗑️  Deleting up to 25 items..."
      aws dynamodb batch-write-item --request-items "$batch" >/dev/null
    done

  # Check for pagination
  LAST_EVALUATED_KEY=$(echo "$SCAN_OUTPUT" | jq -c '.LastEvaluatedKey')
  if [[ "$LAST_EVALUATED_KEY" == "null" ]]; then
    echo "✅ All items deleted from table: $TABLE_NAME"
    break
  fi
done
