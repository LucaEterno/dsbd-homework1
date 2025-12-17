import time
import threading

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30, expected_exception=Exception):
        """
        Initializes a new instance of the CircuitBreaker class.

        Parameters:
        - failure_threshold (int): Number of consecutive failures allowed before opening the circuit.
        - recovery_timeout (int): Time in seconds to wait before attempting to reset the circuit.
        - expected_exception (Exception): The exception type that triggers a failure count increment.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'
        self.lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        """
        Executes the provided function within the circuit breaker context.

        Parameters:
        - func (callable): The function to execute.
        - *args: Variable length argument list for the function.
        - **kwargs: Arbitrary keyword arguments for the function.

        Returns:
        - The result of the function call if successful.

        Raises:
        - CircuitBreakerOpenException: If the circuit is open and calls are not allowed.
        - Exception: Re-raises any exceptions thrown by the function.
        """
        with self.lock:
            if self.state == 'OPEN':
                time_since_failure = time.time() - self.last_failure_time
                if time_since_failure > self.recovery_timeout:
                    print("[CB] Transition OPEN -> HALF_OPEN")
                    self.state = 'HALF_OPEN'
                else:
                    raise CircuitBreakerOpenException("Circuit is open. Call denied.")
            
            try:
                result = func(*args, **kwargs)
            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                raise e
            else:
                if self.state == 'HALF_OPEN':
                    print("[CB] Success in HALF_OPEN -> CLOSED (reset)")
                    self.state = 'CLOSED'
                self.failure_count = 0  # Conta solo failure consecutivi
                return result

class CircuitBreakerOpenException(Exception):
    """Custom exception raised when the circuit breaker is open."""
    pass
