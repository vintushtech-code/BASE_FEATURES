from paymentGatewaySystem.models import PaymentTransaction


class InvalidStateTransitionError(Exception):
    """Raised when an illegal status transition is attempted on a PaymentTransaction."""
    pass


class OptimisticLockError(Exception):
    """Raised when version collision occurs during optimistic concurrency control update."""
    pass


class PaymentStateMachine:
    """
    Strict Finite State Machine enforcing allowed lifecycle transitions for payment transactions.
    
    Allowed Transitions:
      CREATED     -> AUTHORIZED, FAILED
      AUTHORIZED  -> CAPTURED, FAILED
      CAPTURED    -> SETTLED, REFUNDED, FAILED
      SETTLED     -> REFUNDED
      FAILED      -> Terminal (No transitions)
      REFUNDED    -> Terminal (No transitions)
    """

    ALLOWED_TRANSITIONS = {
        'CREATED': {'AUTHORIZED', 'FAILED'},
        'AUTHORIZED': {'CAPTURED', 'FAILED'},
        'CAPTURED': {'SETTLED', 'REFUNDED', 'FAILED'},
        'SETTLED': {'REFUNDED'},
        'FAILED': set(),
        'REFUNDED': set(),
    }

    @classmethod
    def validate_transition(cls, current_status: str, target_status: str):
        """
        Validates whether target_status is a valid transition from current_status.
        """
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid payment state transition: cannot transition from '{current_status}' to '{target_status}'."
            )
        return True

    @classmethod
    def transition(cls, transaction: PaymentTransaction, target_status: str, failure_reason: str = 'NONE', failure_message: str = '') -> PaymentTransaction:
        """
        Executes state transition with Optimistic Concurrency Control (version checking).
        """
        cls.validate_transition(transaction.status, target_status)
        
        current_version = transaction.version
        new_version = current_version + 1
        
        updated_count = PaymentTransaction.objects.filter(
            pk=transaction.pk,
            version=current_version
        ).update(
            status=target_status,
            failure_reason=failure_reason if target_status == 'FAILED' else transaction.failure_reason,
            failure_message=failure_message if target_status == 'FAILED' else transaction.failure_message,
            version=new_version
        )
        
        if updated_count == 0:
            raise OptimisticLockError(
                f"Optimistic lock failure on Transaction {transaction.transaction_id}. Version mismatch (expected {current_version})."
            )
            
        transaction.status = target_status
        transaction.version = new_version
        if target_status == 'FAILED':
            transaction.failure_reason = failure_reason
            transaction.failure_message = failure_message
        return transaction
