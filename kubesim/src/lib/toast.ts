import { toast, ToastOptions as ReactToastifyOptions, cssTransition, Zoom } from 'react-toastify';
import 'animate.css';

// Define a custom slide animation
const slideAnimation = cssTransition({
  enter: 'animate__animated animate__fadeInRight',
  exit: 'animate__animated animate__fadeOutRight'
});

// Custom toast options interface
interface ToastOptions extends ReactToastifyOptions {
  autoClose?: number;
  hideProgressBar?: boolean;
  closeOnClick?: boolean;
  draggable?: boolean;
  style?: React.CSSProperties;
  transition?: typeof Zoom | ReturnType<typeof cssTransition>;
}

// Default options for all toasts
const defaultOptions: ToastOptions = {
  autoClose: 3000,
  hideProgressBar: false,
  closeOnClick: true,
  draggable: true,
  position: "bottom-right",
  className: "rounded-md shadow-lg",
  transition: slideAnimation
};

// Success toast style
const successOptions: ToastOptions = {
  ...defaultOptions,
  style: { 
    background: '#1E40AF', 
    color: 'white', 
    border: '1px solid #1E293B',
    fontWeight: 'bold'
  }
};

// Info toast style
const infoOptions: ToastOptions = {
  ...defaultOptions,
  style: { 
    background: '#0F766E', 
    color: 'white', 
    border: '1px solid #1E293B',
    fontWeight: 'bold'
  }
};

// Error toast style
const errorOptions: ToastOptions = {
  ...defaultOptions,
  autoClose: 5000,
  style: { 
    background: '#9F1239', 
    color: 'white', 
    border: '1px solid #1E293B',
    fontWeight: 'bold'
  }
};

// Node toast notifications
export const notifyNodeAdded = (nodeId: string, cores: number) => {
  toast.success(`Node ${nodeId} with ${cores} cores added successfully! 🚀`, successOptions);
};

export const notifyNodeDeleted = (nodeId: string) => {
  toast.info(`Node ${nodeId} has been removed from the cluster 🗑️`, infoOptions);
};

export const notifyNodeError = (message: string) => {
  toast.error(`Node operation failed: ${message} ❌`, errorOptions);
};

// Pod toast notifications
export const notifyPodLaunched = (podId: string, cpuRequest: number) => {
  toast.success(`Pod ${podId} with ${cpuRequest} CPU cores launched successfully! 🚀`, successOptions);
};

export const notifyPodTerminated = (podId: string) => {
  toast.info(`Pod ${podId} has been terminated successfully 🗑️`, infoOptions);
};

export const notifyPodError = (message: string) => {
  toast.error(`Pod operation failed: ${message} ❌`, errorOptions);
}; 