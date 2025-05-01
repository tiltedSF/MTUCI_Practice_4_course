document.addEventListener('DOMContentLoaded', function() {
    // Обработка формы видео
    const videoForm = document.getElementById('videoForm');
    if (videoForm) {
        videoForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const statusDiv = document.getElementById('videoStatus');
            const resultsDiv = document.getElementById('videoResults');
            
            statusDiv.innerHTML = `
                <div class="progress-container">
                    <p>Processing video...</p>
                    <div class="progress-bar">
                        <div class="progress" id="videoProgress"></div>
                    </div>
                    <p id="progressText">0% completed</p>
                </div>
            `;
            
            fetch('/upload_video', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    statusDiv.innerHTML = `<div class="alert alert-error">Error: ${data.error}</div>`;
                    return;
                }
                
                const progressBar = document.getElementById('videoProgress');
                const progressText = document.getElementById('progressText');
                
                // Проверка статуса каждые 2 секунды
                const checkInterval = setInterval(() => {
                    fetch(`/status/${data.job_id}`)
                    .then(res => res.json())
                    .then(status => {
                        if (status.error) {
                            clearInterval(checkInterval);
                            statusDiv.innerHTML = `<div class="alert alert-error">${status.error}</div>`;
                            return;
                        }
                        
                        progressBar.style.width = `${status.progress}%`;
                        progressText.textContent = `${status.progress}% completed`;
                        
                        if (status.status === 'completed') {
                            clearInterval(checkInterval);
                            statusDiv.innerHTML = '<div class="alert alert-success">Video processing completed!</div>';
                            
                            resultsDiv.innerHTML = `
                                <div class="card">
                                    <h3>Processed Video</h3>
                                    <p>Your video is ready to download.</p>
                                    <a href="${data.download_url}" class="btn btn-secondary">Download Video</a>
                                </div>
                            `;
                        }
                    });
                }, 2000);
            })
            .catch(error => {
                statusDiv.innerHTML = `<div class="alert alert-error">Error: ${error.message}</div>`;
            });
        });
    }
    
    // Анимация кнопок
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', () => {
            btn.style.transform = 'translateY(-2px)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'translateY(0)';
        });
    });
});