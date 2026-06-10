document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const exerciseOptions = document.querySelectorAll('.exercise-option');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const setsInput = document.getElementById('sets');
    const repsInput = document.getElementById('reps');
    const currentExercise = document.getElementById('current-exercise');
    const currentSet = document.getElementById('current-set');
    const currentReps = document.getElementById('current-reps');
    
    // Variables
    let selectedExercise = null;
    let workoutRunning = false;
    let statusCheckInterval = null;
    
    // Select exercise
    exerciseOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Remove selected class from all options
            exerciseOptions.forEach(opt => opt.classList.remove('selected'));
            
            // Add selected class to clicked option
            this.classList.add('selected');
            selectedExercise = this.getAttribute('data-exercise');
        });
    });
    
    // Start workout
    startBtn.addEventListener('click', function() {
        if (!selectedExercise) {
            alert('Please select an exercise first!');
            return;
        }
        
        const sets = parseInt(setsInput.value);
        const reps = parseInt(repsInput.value);
        
        if (isNaN(sets) || sets < 1 || isNaN(reps) || reps < 1) {
            alert('Please enter valid numbers for sets and repetitions.');
            return;
        }
        
        // Start the exercise via API
        fetch('/start_exercise', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exercise_type: selectedExercise,
                sets: sets,
                reps: reps
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                workoutRunning = true;
                startBtn.disabled = true;
                stopBtn.disabled = false;
                
                // Update UI
                currentExercise.textContent = selectedExercise.replace('_', ' ').toUpperCase();
                currentSet.textContent = `1 / ${sets}`;
                currentReps.textContent = `0 / ${reps}`;
                
                // Start status polling
                statusCheckInterval = setInterval(checkStatus, 1000);
            } else {
                alert('Failed to start exercise: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while starting the exercise.');
        });
    });
    
    // Stop workout
    stopBtn.addEventListener('click', function() {
        fetch('/stop_exercise', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                resetWorkoutUI();
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });
    
    // Function to check status
    function checkStatus() {
        fetch('/get_status')
        .then(response => response.json())
        .then(data => {
            if (!data.exercise_running && workoutRunning) {
                // Workout has ended
                resetWorkoutUI();
                return;
            }
            
            // Update status display
            currentSet.textContent = `${data.current_set} / ${data.total_sets}`;
            currentReps.textContent = `${data.current_reps} / ${data.rep_goal}`;
        })
        .catch(error => {
            console.error('Error checking status:', error);
        });
    }
    
    // Reset UI after workout ends
    function resetWorkoutUI() {
        workoutRunning = false;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
        
        currentExercise.textContent = 'None';
        currentSet.textContent = '0 / 0';
        currentReps.textContent = '0 / 0';
    }
});
