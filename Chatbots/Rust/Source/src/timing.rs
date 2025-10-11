use std::time::{Duration, Instant};

/// Convert a `Duration` into milliseconds as `f64`.
pub fn duration_to_milliseconds(duration: Duration) -> f64 {
    (duration.as_secs_f64()) * 1000.0
}

/// A simple stopwatch for measuring elapsed wall-clock time in milliseconds.
#[derive(Debug)]
pub struct Stopwatch {
    start_instant: Option<Instant>,
}

#[allow(dead_code)]
impl Stopwatch {
    /// Create a new, not-yet-started stopwatch.
    pub fn new() -> Self {
        Self { start_instant: None }
    }

    /// Start or restart the stopwatch.
    pub fn start(&mut self) {
        self.start_instant = Some(Instant::now());
    }

    /// Stop the stopwatch and return the elapsed time in milliseconds.
    /// If `start()` was never called, returns `0.0`.
    pub fn stop(&mut self) -> f64 {
        if let Some(actual_start_instant) = self.start_instant.take() {
            let elapsed_duration = actual_start_instant.elapsed();
            duration_to_milliseconds(elapsed_duration)
        } else {
            0.0
        }
    }

    /// Return whether the stopwatch is currently running.
    pub fn is_running(&self) -> bool {
        self.start_instant.is_some()
    }

    /// Reset the stopwatch to the not-started state.
    pub fn reset(&mut self) {
        self.start_instant = None;
    }
}

/// Measure the time a closure takes to run, returning `(result, elapsed_ms)`.
#[allow(dead_code)]
pub fn measure_closure_milliseconds<T, F: FnOnce() -> T>(closure: F) -> (T, f64) {
    let start_instant = Instant::now();
    let result_value = closure();
    let elapsed_milliseconds = duration_to_milliseconds(start_instant.elapsed());
    (result_value, elapsed_milliseconds)
}
