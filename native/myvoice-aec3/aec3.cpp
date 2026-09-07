#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <memory>
#include <stdexcept>
#include "api/echo_canceller3_factory.h"
#include "api/echo_canceller3_config.h"
#include "api/echo_control.h"
#include "audio_processing/audio_buffer.h"
#include "audio_processing/high_pass_filter.h"

namespace py = pybind11;
using Frame = py::array_t<float, py::array::c_style>;

// One instance per stream. No suppression tuning or custom adaptive filter.
class EchoCanceller {
    std::unique_ptr<webrtc::EchoControl> aec;
    webrtc::AudioBuffer near{16000, 1, 16000, 1, 16000, 1};
    webrtc::AudioBuffer far{16000, 1, 16000, 1, 16000, 1};
    webrtc::AudioBuffer linear{16000, 1, 16000, 1, 16000, 1};
    webrtc::HighPassFilter high_pass{16000, 1};
    int delay;

    static void validate(const Frame& frame) {
        if (frame.ndim() != 1 || frame.size() != 160)
            throw std::invalid_argument("Expected one contiguous float32 frame of 160 mono samples");
        for (int i = 0; i < 160; ++i)
            if (!std::isfinite(frame.data()[i]) || std::abs(frame.data()[i]) > 1.0f)
                throw std::invalid_argument("Audio must be finite and normalized to [-1, 1]");
    }

public:
    explicit EchoCanceller(int delay_ms = 0) : delay(delay_ms) {
        if (delay_ms < 0 || delay_ms > 500)
            throw std::invalid_argument("Delay hint must be between 0 and 500 ms");
        webrtc::EchoCanceller3Config config;
        config.filter.export_linear_aec_output = true;
        webrtc::EchoCanceller3Factory factory(config);
        aec = factory.Create(16000, 1, 1);
    }

    py::tuple process(const Frame& mic, const Frame& reference) {
        validate(mic);
        validate(reference);
        Frame linear_out(160), suppressed_out(160);
        const auto* mic_data = mic.data();
        const auto* reference_data = reference.data();
        auto* linear_data = linear_out.mutable_data();
        auto* suppressed_data = suppressed_out.mutable_data();
        {
            py::gil_scoped_release release;
            for (int i = 0; i < 160; ++i) {
                near.channels()[0][i] = mic_data[i] * 32767.0f;
                far.channels()[0][i] = reference_data[i] * 32767.0f;
            }
            // At 16 kHz these buffers each have a single frequency band.
            aec->AnalyzeRender(&far);
            aec->AnalyzeCapture(&near);
            high_pass.Process(&near, true);
            aec->SetAudioBufferDelay(delay);
            aec->ProcessCapture(&near, &linear, false);
            for (int i = 0; i < 160; ++i) {
                linear_data[i] = linear.channels_const()[0][i] / 32767.0f;
                suppressed_data[i] = near.channels_const()[0][i] / 32767.0f;
            }
        }
        return py::make_tuple(linear_out, suppressed_out);
    }

    py::dict metrics() const {
        const auto values = aec->GetMetrics();
        py::dict result;
        result["delay_ms"] = values.delay_ms;
        result["echo_return_loss"] = values.echo_return_loss;
        result["echo_return_loss_enhancement"] = values.echo_return_loss_enhancement;
        return result;
    }
};

PYBIND11_MODULE(myvoice_aec3, module) {
    module.doc() = "WebRTC AEC3: fixed 10 ms mono frames, linear and suppressed output";
    py::class_<EchoCanceller>(module, "EchoCanceller")
        .def(py::init<int>(), py::arg("delay_ms") = 0)
        .def("process", &EchoCanceller::process, py::arg("mic").noconvert(), py::arg("reference").noconvert())
        .def_property_readonly("metrics", &EchoCanceller::metrics);
}
